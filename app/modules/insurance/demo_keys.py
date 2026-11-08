"""演示用国密密钥（仅限本地开发演示，严禁用于生产环境！）。

- HIS 侧：用自己的私钥签名请求，用医保平台公钥验签响应
- 平台侧：用自己的私钥签名响应，用 HIS 公钥验签请求
- SM4 对称密钥双方共享，用于报文加解密（生产环境应通过密钥协商/安全注入）

生产接入时这些值全部改为环境变量注入的真实密钥。
"""

HIS_PRIVATE = "b2d8baa9cc6492ccd0f005714ee06076"
HIS_PUBLIC = (
    "0d1e8c0193ef0f556b359e2eb20983654a818b430b88e9c9703ef07a02b2f230"
    "ae92c7894c6f03d6f4eac62dfd8046ef382c06f170a8b351fb86351ed5fee6a4"
)

PLATFORM_PRIVATE = "7e471d17c6cfc140577c907efbfe9de9"
PLATFORM_PUBLIC = (
    "66c36525cae1100b76e004e98a0bd6c48db49ffd4f966c7d01a51bcf4ff26335"
    "0341c9f506b6156ce39e8e3bae46d9f3f87e8d6df83ffdf0e777da8ce24b2dd0"
)

SM4_KEY = "fe38d82c061146038e5a02134492982e"
