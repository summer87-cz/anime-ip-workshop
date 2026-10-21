# 出图通道适配器 / Adapters

本 skill **不实现、不打包、也不推荐特定出图服务**。你需要自己提供一个"能用命令行调用"的出图能力，然后把它配置成命令模板。

---

## 一、需要提供两种能力

| 能力 | 用途 | 是否必需 |
|---|---|---|
| **text-to-image**（文生图） | 无照片时的首图、纯背景元素 | 可选 |
| **image-to-image**（图生图 / 参考图编辑） | 三视图、表情包、场景延伸、局部修改 | **必需** |

**图生图是硬门槛**：整个一致性方法论建立在"每次都以上一张已确认的图作为参考输入"之上。如果你的通道图生图接口会忽略参考图字段（等同于没传），那它不满足要求。

---

## 二、命令模板契约

在环境变量里配置两个模板，占位符会被替换：

```bash
T2I_CMD='<你的文生图命令> --prompt "{prompt}" --size {size} --out {outdir}'
I2I_CMD='<你的图生图命令> --prompt "{prompt}" --ref "{ref}" --size {size} --out {outdir}'
```

**占位符约定**

- `{prompt}` —— 完整提示词（含正向描述与反向串），可能很长，**必须整体传入，不要截断**
- `{ref}` —— 参考图绝对路径
- `{size}` —— `1024x1536` / `1024x1024` / `1536x1024` 之一
- `{outdir}` —— 输出目录（已存在）

**对脚本的要求**

1. 生成文件写入 `{outdir}`，文件名任意，但**必须真实落盘**；
2. 正常结束返回退出码 0，失败返回非 0 并把错误打到 stderr；
3. 单张耗时 30-90 秒属正常，**不要在 30 秒就超时中断**；
4. 一次返回多张时不要覆盖同名文件（本 skill 会逐张过目再挑选）。

---

## 三、HTTP API 接入示例

如果你的服务是 HTTP 接口，写一个小脚本包一层，再填进命令模板即可。下面是通用骨架（以 Python 为例，需自行替换端点、鉴权与字段名——**各平台字段差异很大，不要照抄**）：

```python
#!/usr/bin/env python3
"""最小图生图封装：把 API 响应落盘成图片文件。"""
import base64, os, sys, json, urllib.request

API_URL = os.environ["T2I_API_URL"]          # 你的端点
API_KEY = os.environ["T2I_API_KEY"]          # 你的密钥（勿写死在代码里）

def main():
    prompt, ref, size, outdir = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    with open(ref, "rb") as f:
        ref_b64 = base64.b64encode(f.read()).decode()

    payload = {
        "model": os.environ.get("T2I_MODEL", "your-model-name"),
        "prompt": prompt,
        "size": size,
        "image": f"data:image/png;base64,{ref_b64}",   # 字段名视平台而定
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.load(resp)

    # 响应可能是 b64 或 URL，两种都要处理
    item = data["data"][0]
    if "b64_json" in item:
        raw = base64.b64decode(item["b64_json"])
    else:
        raw = urllib.request.urlopen(item["url"], timeout=120).read()

    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, f"out_{os.getpid()}.png")
    open(out, "wb").write(raw)
    print(out)

if __name__ == "__main__":
    main()
```

配置：

```bash
export T2I_API_URL='https://your-endpoint/v1/images/edits'
export T2I_API_KEY='...'     # 用密钥管理，不要提交进仓库
export I2I_CMD='python i2i.py "{prompt}" "{ref}" {size} {outdir}'
```

---

## 四、常见坑

**参考图不生效。** 有些中转/代理服务会静默忽略 `image` 字段，返回一张"和你给的角色毫无关系"的图。验证方法：拿一张辨识度极高的图（比如纯红底加黑字）作参考，提示词写"保持参考图不变"，如果出来的不是那张图，说明参考图通道没生效。

**尺寸被强制改写。** 部分服务会把非常规尺寸压到 1024x1024。若发现竖版被压扁，改用该服务支持的成对尺寸。

**长提示词被截断。** 有些网关有字符上限，超长会 502 或静默截断。本 skill 的提示词通常在 600-1200 字，若你的通道上限更低，需要把"反向串"和"画风句"精简后再试。

**内容是空的。** 部分服务对真人图像有内容审核，可能返回 policy 拒绝。处理方式见 `SKILL.md` 的"通道安全与素材铁律"三级降级。

---

## 五、不需要的东西

- 不需要把密钥写进本仓库任何文件；
- 不需要修改 `SKILL.md`——它只引用环境变量名；
- 不需要提供示例图。
