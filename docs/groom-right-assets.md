# 右侧舔手素材

这套素材抬起画面右侧的橘色前臂，画面左侧白色前爪保持落地。没有镜像整只猫。左侧原素材、原 manifest 和十二张运行帧均保持原样。

运行资源由 `assets/groom/v2.1/manifest-right.json` 重建，输出目录约定为 `assets/groom/v2.1/runtime-right/`。每帧是 640×768 RGBA；第 0、11 帧直接使用真实默认合成器，RGBA SHA-256 为 `e02f052cb970d2ebed4946ad0f09038adbce4d41da3a730e09e56783054e5eb0`。

```sh
python tools/import_groom_frames.py --manifest assets/groom/v2.1/manifest-right.json --output assets/groom/v2.1/runtime-right
python tools/verify_groom_right_assets.py --frames assets/groom/v2.1/runtime-right
```

十二张姿态依次为默认、抬爪、靠近嘴、伸舌、舔舐一、舔舐二、舔舐三、收舌、离嘴、放下一、放下二、默认。沿用播放器的 75 ms 时长与序列 `(0,1,2) + (3,4,5,6,7,8) * repetitions + (9,10,11)`，重复次数由公共运行时选择。

素材来源保存在两份文本编码 PNG 中：

- `source/groom-right-approved.png.b64`：恢复的 1180×1333、4×3 原彩色姿态与配套遮罩。输入文件 SHA 分别为 `d0241556bdb3ab2c0def893b1a7c08f54972a4d1d49342ccd8c49ee201cb1e56`、`a1b58e4e492739b024088e74a50dda47123fca0092abb72d327629cf41bfacaa`。
- `source/groom-right-underbelly.png.b64`：为移开原前爪后的胸腹、内腿区域单独生成的局部补图。生成输入 SHA 为 `58b4a5c48257c0c29639b58c0db3f935a85bbc81a42070f653ba7efcf46867fe`。仅保留配准后的 191×156 局部，不替换整猫。

导入器以实际默认帧为底板，只替换生成的嘴舌、右前肢和显露胸腹。原图中的额外脚掌和嘴下装饰不进入画面。局部替换使用 RGBA 覆盖，透明空隙会清除旧脚；全程保留头部、耳朵、背部和臀部的位置。外轮廓洋红污染只在新区域去色，不侵蚀透明轮廓。

验证记录：十二帧含十一张不同 RGBA，首尾逐像素等于真实默认帧；局部范围外所有 RGBA 像素固定；抬爪阶段旧脚位置为空；嘴下无残片；腹部新轮廓无洋红污染。左侧在导入器修改前后分别重建，十二个 PNG 文件逐字节一致。黑白底联系表和三次舔舐预览已进行画面检查，预览不重复存入仓库。

The source key `right` retains its historical atlas coordinate label. The visible command is 橘色前爪舔手（3次）; it does not assert anatomical right. The older `left` pack is shown as 白色前爪舔手（3次）.
