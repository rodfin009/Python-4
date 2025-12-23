from openai import OpenAI
import os
import json

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.environ.get("NVIDIA_API_KEY")
)

# تعريف النماذج والمعاملات المسموحة لكل واحد بدقة
MODELS_CONFIG = {
    "deepseek": {
        "id": "deepseek-ai/deepseek-v3.2",
        "defaults": {"temperature": 1.0, "top_p": 0.95, "max_tokens": 8192, "stream": True},
        # السماح بمعامل التفكير الخاص بديب سيك
        "allowed_params": ["temperature", "top_p", "max_tokens", "stream", "deepseek_thinking"]
    },
    "moonshot": {
        "id": "moonshotai/kimi-k2-thinking",
        "defaults": {"temperature": 0.19, "top_p": 0.71, "max_tokens": 16384, "stream": True},
        "allowed_params": ["temperature", "top_p", "max_tokens", "stream"]
    },
    "mistral": {
        "id": "mistralai/mistral-large-3-675b-instruct-2512",
        "defaults": {"temperature": 0.15, "top_p": 0.70, "max_tokens": 8192, "stream": True, "frequency_penalty": 0.0, "presence_penalty": 0.0},
        "allowed_params": ["temperature", "top_p", "max_tokens", "stream", "frequency_penalty", "presence_penalty"]
    },
    "gpt_oss": {
        "id": "openai/gpt-oss-120b",
        "defaults": {"temperature": 0.23, "top_p": 0.72, "max_tokens": 4096, "stream": True},
        "allowed_params": ["temperature", "top_p", "max_tokens", "stream"]
    }
}

def generate_response(model_key, messages, user_settings=None, use_search=False):
    # التحقق من وجود المفتاح
    if not os.environ.get("NVIDIA_API_KEY"):
        yield "__TEXT__❌ خطأ: لم يتم العثور على NVIDIA_API_KEY."
        return

    config = MODELS_CONFIG.get(model_key, MODELS_CONFIG["deepseek"])
    params = config["defaults"].copy()

    # معالجة الإعدادات القادمة من الواجهة
    if user_settings:
        for key, value in user_settings.items():
            # نأخذ فقط المعاملات المسموحة لهذا النموذج
            if key in config["allowed_params"] and value is not None and value != "":

                # 1. تفعيل Thinking الخاص بـ DeepSeek
                if key == "deepseek_thinking" and model_key == "deepseek":
                    if str(value).lower() == 'true':
                        params["extra_body"] = {"chat_template_kwargs": {"thinking": True}}

                # 2. تحويل Stream إلى Boolean
                elif key == "stream":
                    params[key] = (str(value).lower() == 'true')

                # 3. باقي الأرقام
                else:
                    try:
                        params[key] = float(value)
                    except: pass

    # إضافة ملاحظة البحث (محاكاة)
    if use_search:
        messages[0]["content"] += "\n[System: Internet Search Enabled. Provide real-time info.]"

    try:
        completion = client.chat.completions.create(
            model=config["id"],
            messages=messages,
            **params
        )

        # وضع البث (Stream)
        if params.get("stream"):
            for chunk in completion:
                if not chunk.choices: continue
                delta = chunk.choices[0].delta

                # التقاط التفكير (Reasoning)
                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning:
                    yield f"__THINK__{reasoning}"

                # التقاط النص العادي (Content)
                content = delta.content
                if content:
                    yield f"__TEXT__{content}"

        # وضع عدم البث (دفعة واحدة)
        else:
            msg = completion.choices[0].message.content
            yield f"__TEXT__{msg}"

    except Exception as e:
        yield f"__TEXT__⚠️ خطأ في النموذج: {str(e)}"
