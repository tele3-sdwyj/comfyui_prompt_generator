# comfyui_prompt_generator
A small tool for crafting prompts using LLMs and text references.
🌟 核心特性双轨提示词输出 (tag_prompt & prose_prompt)：tag_prompt：输出结构化的 Danbooru Tag 流，完美适配 Illustrious、AnimeXL、SDXL、SD 1.5 等模型。prose_prompt：输出富有画面感与构图细节的连贯英文长句，完美适配 FLUX.1、SD3、Midjourney 等模型。三种 LLM 后台部署方案：Online API：支持 DeepSeek、SiliconFlow 等 OpenAI 兼容接口。Local API：支持 Ollama、LM Studio 等本地轻量化大模型服务（如 Qwen2.5:1.5b）。Direct Local Model：直接加载 ComfyUI models/text_encoders/ 目录下的 Hugging Face 格式模型（如 Qwen 系列）。角色知识库支持 (character_library)：自动匹配角色名称/别名/特征，精准锁定角色官方 Tag 与外观描写。风格少样本范例 (reference_library)：通过本地示例文件引导演示，大幅提升光影、构图与画风控制力。Danbooru 实时标签检索：可选择性开启在线 API 抓取，携带凭证鉴权，补充极具时效性的离散 Tag。📁 目录结构PlaintextComfyui_prompt_generator/
├── __init__.py                  # 插件入口文件
├── prompt_generator_v2.py       # 核心节点逻辑
├── config.json                  # 配置文件（存放 API Key 及服务器路径）
├── README.md                    # 说明文档
├── reference_library/           # [本地] 风格参考库 (.txt / .json)
│   └── anime_general.txt
└── character_library/           # [本地] 角色知识库 (.txt / .json)
    └── character_db.txt
⚙️ 配置文件说明 (config.json)在插件根目录下创建或编辑 config.json 文件：JSON{
  "db_name": "your_danbooru_username",
  "db_apikey": "your_danbooru_api_key",

  "llm_url": "https://api.deepseek.com/v1/chat/completions",
  "llm_apikey": "sk-your-deepseek-api-key",
  "llm_model": "deepseek-chat",

  "local_api_url": "http://127.0.0.1:11434/v1/chat/completions",
  "local_api_model": "qwen2.5:1.5b"
}
注意：请勿将包含实际 llm_apikey 或 db_apikey 的 config.json 上传至公共代码仓库。🚀 安装与启动将整个插件文件夹放入 ComfyUI 的 custom_nodes 目录下：PlaintextComfyUI/custom_nodes/Comfyui_prompt_generator/
确保配置好 config.json。   如需使用 Direct Local Model 模式，请将支持 Chat Template 的 Hugging Face 格式模型（如 Qwen2.5-1.5B-Instruct）放入 ComfyUI 的文本编码器路径中：PlaintextComfyUI/models/text_encoders/Qwen2.5-1.5B-Instruct/
彻底重启 ComfyUI 控制台（关闭 CMD/Terminal 窗口后重新运行启动脚本）。在 ComfyUI 画布中双击或右键搜寻 Universal Multi-Ref & LLM Prompt Generator（位于 Inspiration 分类下）。📖 节点参数指南参数名称类型 / 选项说明seedINT随机种子，控制变体生成。custom_themeSTRING画面核心主题、故事背景或角色名称。llm_backendENUM选择生成后台：在线 API / 本地 API (Ollama) / 本地模型直载。local_model_folderENUM当使用直载模式时，选择 models/text_encoders/ 下的文件夹。style_presetENUM画面视觉预设（如日系插画、赛博朋克、暗黑奇幻、写实摄影）。reference_fileFILEreference_library/ 目录下用于 Few-shot 学习的风格示例文件。character_library_fileFILEcharacter_library/ 目录下存放的角色定义文件。use_danbooruENUM是否开启 Danbooru 在线 Tag 抓取。danbooru_ratingENUMDanbooru 抓取时的分级过滤器 (general, sensitive 等)。tag_prefixSTRING自动拼接到 tag_prompt 最前面的质量前缀词。prose_prefixSTRING自动拼接到 prose_prompt 最前面的前缀。💡 使用小贴士角色库书写格式建议（放置于 character_library/）：Plaintext# 角色名, 别名 | Danbooru标准Tag | 视觉特征描述
初音未来, Miku | 1girl, hatsune miku, long hair, twintails, aqua hair, aqua eyes | Hatsune Miku with long aqua twintails and teal eyes
显存优化：使用在线 API 或 Ollama 本地 API 时，零额外显存占用。使用 Direct Local Model 模式时，节点在生成完成后会自动释放显存并清理 PyTorch 缓存，避免影响后续 KSampler 渲染。
