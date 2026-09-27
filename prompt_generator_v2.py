import os, json, random, re, requests

# 尝试导入 ComfyUI 内置路径管理与 PyTorch
try:
    import folder_paths
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

# --- 1. 读取配置文件 ---
current_dir = os.path.dirname(os.path.realpath(__file__))
config_path = os.path.join(current_dir, "config.json")
if not os.path.exists(config_path):
    config_path = os.path.join(current_dir, "config_2.json")

def load_config():
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[PromptGen] 读取配置文件失败: {e}")
        return {}

CONFIG = load_config()

# 目录定义
REF_LIBRARY_DIR = os.path.join(current_dir, "reference_library")
CHAR_LIBRARY_DIR = os.path.join(current_dir, "character_library")
os.makedirs(REF_LIBRARY_DIR, exist_ok=True)
os.makedirs(CHAR_LIBRARY_DIR, exist_ok=True)

def get_files_from_dir(target_dir, default_filename, default_content):
    files = [f for f in os.listdir(target_dir) if f.endswith(".txt") or f.endswith(".json")]
    if not files:
        default_path = os.path.join(target_dir, default_filename)
        with open(default_path, "w", encoding="utf-8") as f:
            f.write(default_content)
        files = [default_filename]
    return files

def load_file_content(target_dir, filename):
    if filename == "none" or not filename:
        return ""
    fpath = os.path.join(target_dir, filename)
    if os.path.exists(fpath):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            print(f"[PromptGen] 读取文件 {filename} 失败: {e}")
    return ""

def get_local_text_encoders():
    """扫描 ComfyUI models/text_encoders 文件夹"""
    model_dirs = ["none"]
    if 'folder_paths' in globals():
        te_path = folder_paths.get_folder_paths("text_encoders")
        for p in te_path:
            if os.path.exists(p):
                for item in os.listdir(p):
                    full_p = os.path.join(p, item)
                    if os.path.isdir(full_p):
                        model_dirs.append(item)
    return model_dirs

# --- Danbooru API 真实请求模块 ---
def fetch_danbooru_tags(theme_query, rating, db_name, db_apikey):
    """带账号鉴权的 Danbooru API 标签抓取函数"""
    if not theme_query.strip():
        return ""

    # 清理查询词，提取关键字（Danbooru 搜索空格分隔）
    clean_query = re.sub(r'[^\w\s]', ' ', theme_query).strip()
    words = clean_query.split()
    if not words:
        return ""

    # 构造 Danbooru search tag（取前1-2个核心词组合）
    search_tag = words[0].lower()
    tags_param = f"{search_tag}"
    if rating != "all":
        tags_param += f" rating:{rating}"

    url = "https://danbooru.donmai.us/posts.json"
    params = {
        "tags": tags_param,
        "limit": 3,
        "random": "true"
    }

    # 填入配置中的 API 凭证
    if db_name and db_apikey:
        params["login"] = db_name
        params["api_key"] = db_apikey

    headers = {"User-Agent": "ComfyUI-PromptGen/1.0"}

    try:
        print(f"[PromptGen] 正在请求 Danbooru API (Tag: {tags_param})...")
        resp = requests.get(url, params=params, headers=headers, timeout=8)
        if resp.status_code == 200:
            posts = resp.json()
            extracted_tags = set()
            for post in posts:
                # 抓取角色 Tag 与通用特征 Tag
                for category in ['tag_string_character', 'tag_string_general', 'tag_string_copyright']:
                    if category in post and post[category]:
                        extracted_tags.update(post[category].split())
            
            if extracted_tags:
                # 随机挑选 25 个以内不重复 Tag，避免提示词过长
                sampled = random.sample(list(extracted_tags), min(25, len(extracted_tags)))
                print(f"[PromptGen] Danbooru 抓取成功，获取 {len(sampled)} 个关联 Tag。")
                return ", ".join(sampled)
        else:
            print(f"[PromptGen Warning] Danbooru API 返回状态码: {resp.status_code}")
    except Exception as e:
        print(f"[PromptGen Warning] Danbooru 网络请求失败或超时: {e}")
    
    return ""

# ----------------------------------------------------------------
# 核心节点类
# ----------------------------------------------------------------
class UniversalMultiRefPromptGenerator:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        default_ref = "1girl, solo, white hair, glowing eyes, masterpiece, cinematic lighting\n"
        default_char = "# 角色名 | Tags | 描述\n初音未来, Miku | 1girl, hatsune miku, long hair, twintails, aqua hair | Hatsune Miku\n"
        
        ref_files = get_files_from_dir(REF_LIBRARY_DIR, "anime_general.txt", default_ref)
        char_files = get_files_from_dir(CHAR_LIBRARY_DIR, "character_db.txt", default_char)
        local_models = get_local_text_encoders()

        return {
            "required": {
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "custom_theme": ("STRING", {
                    "default": "", 
                    "multiline": False, 
                    "placeholder": "主题/角色/故事（如: 少年，少女）"
                }),
                "llm_backend": ([
                    "Online API (DeepSeek/SiliconFlow)", 
                    "Local API (Ollama / LM Studio)", 
                    "Direct Local Model (Transformers)"
                ], {"default": "Online API (DeepSeek/SiliconFlow)"}),
                "local_model_folder": (local_models, {"default": local_models[0]}),
                "style_preset": ([
                    "Auto / Follow Reference File", 
                    "Japanese Anime / Illustration", 
                    "Cyberpunk / Sci-Fi", 
                    "Dark Fantasy / Gothic", 
                    "Realistic Photo / Cinematic"
                ], {"default": "Auto / Follow Reference File"}),
                "reference_file": (ref_files, {"default": ref_files[0] if ref_files else "none"}),
                "character_library_file": (["none"] + char_files, {"default": char_files[0] if char_files else "none"}),
                "use_danbooru": (["disable", "enable"], {"default": "disable"}),
                "danbooru_rating": (["general", "sensitive", "questionable", "explicit", "all"], {"default": "general"}),
                "tag_prefix": ("STRING", {"default": "masterpiece, best quality, ", "multiline": False}),
                "prose_prefix": ("STRING", {"default": "", "multiline": False}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("tag_prompt", "prose_prompt")
    FUNCTION = "generate_prompts"
    CATEGORY = "Inspiration"

    def call_transformers_local(self, model_folder_name, system_prompt, user_prompt):
        if not HAS_TRANSFORMERS:
            raise ImportError("未检测到 transformers 或 PyTorch 环境！")
        
        te_paths = folder_paths.get_folder_paths("text_encoders")
        model_path = None
        for p in te_paths:
            candidate = os.path.join(p, model_folder_name)
            if os.path.exists(candidate):
                model_path = candidate
                break

        if not model_path:
            raise FileNotFoundError(f"未找到本地模型目录: {model_folder_name}")

        print(f"[PromptGen] 正在加载本地大模型: {model_path} ...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            model_path, 
            torch_dtype=torch.float16 if device == "cuda" else torch.float32, 
            device_map="auto", 
            trust_remote_code=True
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        model_inputs = tokenizer([text], return_tensors="pt").to(device)

        generated_ids = model.generate(**model_inputs, max_new_tokens=512, temperature=0.7)
        generated_ids = [output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)]
        response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

        del model
        del tokenizer
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        return response

    def generate_prompts(self, seed, custom_theme, llm_backend, local_model_folder, style_preset, reference_file, character_library_file, use_danbooru, danbooru_rating, tag_prefix, prose_prefix):
        random.seed(seed)

        ref_text = load_file_content(REF_LIBRARY_DIR, reference_file)
        char_text = load_file_content(CHAR_LIBRARY_DIR, character_library_file)

        # 获取 Danbooru API 数据（如果开启）
        danbooru_fetched_tags = ""
        if use_danbooru == "enable" and custom_theme.strip():
            db_name = CONFIG.get("db_name", "")
            db_apikey = CONFIG.get("db_apikey", "")
            danbooru_fetched_tags = fetch_danbooru_tags(custom_theme, danbooru_rating, db_name, db_apikey)

        # 构建完整的 Context
        system_prompt = f"""You are an elite AI Image Prompt Engineer.
Your goal: Generate TWO prompts (Tag Style & Natural Prose Style) matching the user's theme, character database, and target style.

--- TARGET STYLE PRESET ---
Style: {style_preset}

--- CHARACTER KNOWLEDGE BASE ---
{char_text if char_text else "None provided."}

--- DANBOORU REAL-TIME TAG REFERENCE (Extracted from real Danbooru API for accuracy) ---
{danbooru_fetched_tags if danbooru_fetched_tags else "None fetched or feature disabled."}

--- STYLE & COMPOSITION REFERENCE EXAMPLES ---
{ref_text if ref_text else "Standard high quality image generation rules."}

--- OUTPUT FORMAT REQUIREMENTS ---
Respond ONLY with a valid JSON object:
{{
  "tag_prompt": "comma-separated Danbooru tags (for Illustrious/SDXL)",
  "prose_prompt": "detailed, vivid natural language sentences (for FLUX.1/SD3)"
}}

RULES:
1. 'tag_prompt': Strict comma-separated tags ([Character Tags] -> [Outfit/Props] -> [Pose/Action] -> [Environment] -> [Lighting]).
2. 'prose_prompt': 2-3 cinematic descriptive sentences.
"""

        user_msg = []
        if custom_theme.strip():
            user_msg.append(f"User Request Theme/Character: '{custom_theme.strip()}'")
        else:
            user_msg.append("User Request Theme: Random creative scene.")
        user_msg.append(f"Random Seed: {seed}")
        user_prompt_str = "\n".join(user_msg)

        content = ""

        try:
            # 模式 1：在线 API
            if llm_backend == "Online API (DeepSeek/SiliconFlow)":
                headers = {"Authorization": f"Bearer {CONFIG.get('llm_apikey', '')}", "Content-Type": "application/json"}
                payload = {
                    "model": CONFIG.get("llm_model", "deepseek-chat"),
                    "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt_str}],
                    "temperature": 0.85
                }
                resp = requests.post(CONFIG.get("llm_url", ""), json=payload, headers=headers, timeout=25)
                resp.raise_for_status()
                content = resp.json()['choices'][0]['message']['content'].strip()

            # 模式 2：本地 API (Ollama / LM Studio)
            elif llm_backend == "Local API (Ollama / LM Studio)":
                local_url = CONFIG.get("local_api_url", "http://127.0.0.1:11434/v1/chat/completions")
                local_model = CONFIG.get("local_api_model", "qwen2.5:1.5b")
                payload = {
                    "model": local_model,
                    "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt_str}],
                    "temperature": 0.7
                }
                resp = requests.post(local_url, json=payload, timeout=30)
                resp.raise_for_status()
                content = resp.json()['choices'][0]['message']['content'].strip()

            # 模式 3：直接加载 models/text_encoders 下的模型
            elif llm_backend == "Direct Local Model (Transformers)":
                content = self.call_transformers_local(local_model_folder, system_prompt, user_prompt_str)

            # JSON 清理解析
            content = re.sub(r"^```json\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"^```\s*", "", content)
            content = re.sub(r"\s*```$", "", content).strip()

            res_json = json.loads(content)
            raw_tag = res_json.get("tag_prompt", "").strip()
            raw_prose = res_json.get("prose_prompt", "").strip()

            return (tag_prefix + raw_tag, prose_prefix + raw_prose)

        except Exception as e:
            print(f"[UniversalPromptGen Error]: {e}")
            fallback = custom_theme.strip() if custom_theme.strip() else "1girl, solo, anime style"
            return (
                tag_prefix + f"{fallback}, dynamic lighting, detailed",
                prose_prefix + f"A captivating scene featuring {fallback} with cinematic lighting."
            )

NODE_CLASS_MAPPINGS = {
    "UniversalMultiRefPromptGenerator": UniversalMultiRefPromptGenerator
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "UniversalMultiRefPromptGenerator": "Universal Multi-Ref & LLM Prompt Generator"
}