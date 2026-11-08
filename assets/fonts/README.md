# Fonts

Self-hosted WOFF2 files, taken from official upstream sources only. No remote
font service is used. All three families are licensed under the SIL Open Font
License 1.1; see the `OFL-*.txt` files in this folder.

## Inter

- Source: <https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip>
  (release tag `v4.1`)
- Archive SHA-256: `9883fdd4a49d4fb66bd8177ba6625ef9a64aa45899767dde3d36aa425756b11e`
- `Inter-Regular.woff2` (from `web/`):
  `e06f6b1bc553aaea4e4668023ed0ab0a147129c3107f511bc7d03d361b0ae085`
- `Inter-Bold.woff2` (from `web/`):
  `fa888127b6da015b65569f0351f3b5c391ad928904951f1c20e9f8462a8d95ea`
- `OFL-Inter.txt` (from `LICENSE.txt`):
  `262481e844521b326f5ecd053e59b98c8b2da78c8ee1bdbb6e8174305e54935a`

## IBM Plex Mono

- Source: <https://github.com/IBM/plex/releases/download/%40ibm%2Fplex-mono%402.5.0/ibm-plex-mono.zip>
  (release tag `@ibm/plex-mono@2.5.0`)
- Archive SHA-256: `6d23f01257663d8cc49a0d64c22ced630b79e0e2a0ac08a0da86e9a38bbc481c`
- `IBMPlexMono-Regular-Latin1.woff2` (from `ibm-plex-mono/fonts/split/woff2/`):
  `e8993d946649b9d01abb1ed06d574b19d8ea3e66b5c3948602db335c44c18e56`
- `IBMPlexMono-Medium-Latin1.woff2` (from `ibm-plex-mono/fonts/split/woff2/`):
  `41201b658a328b9d00368215c2f1102770f80b15952ab82631e4006255e6365d`
- `OFL-IBM-Plex-Mono.txt` (from `ibm-plex-mono/LICENSE.txt`):
  `7e6b2818edbd8f6a01ae80641cc8f16a51080d08fb4e532be3a0b6f74adb07da`

## Cinzel

- Source: `ofl/cinzel/` in <https://github.com/google/fonts>, pinned to commit
  `3dd78844021e948ceb633d1dcee3f7885561b5d9`
- `Cinzel[wght].ttf` SHA-256:
  `f4d83d34d1f6c741193e4acf4b3dff9531e5a67b6aa65228d00a7db72a4e0f34`
- `Cinzel-wght.woff2`, converted with
  `uv run --with fonttools --with brotli python -m fontTools.ttLib.woff2 compress <ttf> -o <woff2>`:
  `2ab8b19811f4842ad4c9d168f934ef046355e81a3a6f36e15fe7a4abe38239d3`
  (a different fontTools or brotli version may produce a different hash)
- `OFL-Cinzel.txt` (from `OFL.txt`, unchanged):
  `f2b3029aba64c378bf0963b62945eee15e564fe4330b934c8f2eb058282b5e83`
