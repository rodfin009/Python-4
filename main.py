import os, subprocess
from flask import Flask, Response, stream_with_context, request, jsonify
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=os.environ.get("NVIDIA_API_KEY"))

# إعداد هوية Git لضمان عمل زر النشر
subprocess.run(["git", "config", "--global", "user.email", "agent@replit.com"], check=False)
subprocess.run(["git", "config", "--global", "user.name", "AI Agent"], check=False)
subprocess.run(["git", "config", "--global", "credential.helper", "store"], check=False)

# لاحظ: استخدمنا Raw String (r) لتجنب تداخل الرموز
HTML_PAGE = r"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Workspace</title>
    <style>
        * { box-sizing: border-box; }
        body { background: #0d1117; color: #e6edf3; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }

        /* الشات */
        #chat { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 20px; scroll-behavior: smooth; padding-bottom: 120px; }

        .msg { padding: 12px 18px; border-radius: 12px; max-width: 85%; line-height: 1.6; font-size: 15px; position: relative; word-wrap: break-word; }
        .user-msg { background: #1f6feb; color: white; align-self: flex-start; border-bottom-right-radius: 4px; }
        .ai-msg { background: #161b22; border: 1px solid #30363d; align-self: flex-end; border-bottom-left-radius: 4px; width: fit-content; }

        /* صندوق التفكير */
        .thinking-box {
            background: rgba(22, 27, 34, 0.5);
            border: 1px dashed #30363d;
            border-radius: 8px;
            width: 100%;
            align-self: flex-end;
            margin-top: 5px;
            overflow: hidden;
        }
        .thinking-header {
            padding: 8px 12px;
            font-size: 12px;
            color: #8b949e;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            background: #161b22;
        }
        .thinking-content {
            display: none;
            padding: 10px;
            font-family: monospace;
            font-size: 12px;
            color: #79c0ff;
            max-height: 200px; /* تحديد طول التفكير */
            overflow-y: auto;  /* تفعيل السكرول للتفكير */
            background: #0d1117;
            white-space: pre-wrap;
            border-top: 1px solid #30363d;
        }

        /* كارت التحكم */
        .code-card { background: #0d1117; border: 1px solid #30363d; border-radius: 8px; margin-top: 10px; overflow: hidden; width: 100%; }
        .card-header { background: #161b22; padding: 10px; font-size: 13px; color: #e6edf3; border-bottom: 1px solid #30363d; display: flex; justify-content: space-between; align-items: center; }
        .card-actions { padding: 10px; display: flex; gap: 8px; }

        .btn { flex: 1; padding: 12px; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; color: white; display: flex; align-items: center; justify-content: center; gap: 5px; font-size: 14px; transition: 0.2s; }
        .btn-preview { background: #238636; } /* أخضر للمعاينة */
        .btn-publish { background: #1f6feb; } /* أزرق للنشر */
        .btn-reject { background: #da3633; flex: 0.3; } /* أحمر للرفض */

        .btn:active { transform: scale(0.95); }

        /* منطقة الإدخال */
        .input-area { position: fixed; bottom: 0; left: 0; right: 0; background: #010409; padding: 15px; border-top: 1px solid #30363d; display: flex; gap: 10px; align-items: center; z-index: 50; }
        input { flex: 1; padding: 14px; background: #0d1117; border: 1px solid #30363d; border-radius: 25px; color: white; outline: none; font-size: 16px; padding-left: 20px; padding-right: 20px; }
        .send-btn { width: 45px; height: 45px; border-radius: 50%; background: #1f6feb; color: white; border: none; font-size: 18px; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; transform: rotate(180deg); }

        /* نافذة المعاينة */
        #previewModal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.95); z-index: 100; flex-direction: column; }
        .modal-bar { height: 50px; background: #161b22; display: flex; align-items: center; justify-content: space-between; padding: 0 15px; border-bottom: 1px solid #30363d; color: white; }
        .close-preview { background: none; border: none; color: #ff7b72; font-size: 28px; cursor: pointer; }
        iframe { flex: 1; width: 100%; border: none; background: white; }
    </style>
</head>
<body>

    <div id="chat"></div>

    <div class="input-area">
        <button class="send-btn" onclick="send()">➤</button>
        <input type="text" id="userInput" placeholder="اطلب أي شيء..." autocomplete="off">
    </div>

    <div id="previewModal">
        <div class="modal-bar">
            <span>معاينة حية</span>
            <button class="close-preview" onclick="closePreview()">×</button>
        </div>
        <iframe id="previewFrame"></iframe>
    </div>

    <script>
        const chat = document.getElementById('chat');
        const input = document.getElementById('userInput');
        const modal = document.getElementById('previewModal');
        const iframe = document.getElementById('previewFrame');

        // رسالة ترحيب عند الفتح
        window.onload = () => {
            setTimeout(() => {
                chat.innerHTML += `<div class="msg ai-msg">مرحباً! أنا وكيلك الذكي. 🤖<br>يمكنك طلب إنشاء موقع، كود بايثون، أو أي مهمة برمجية.</div>`;
            }, 500);
        };

        async function send() {
            const text = input.value.trim();
            if (!text) return;

            input.value = "";
            // إصلاح مشكلة ظهور {text}
            chat.innerHTML += `<div class="msg user-msg">${text.replace(/</g, "&lt;")}</div>`;
            chat.scrollTop = chat.scrollHeight;

            // إنشاء عنصر التفكير
            const thinkingId = "think-" + Date.now();
            const aiDiv = document.createElement('div');
            aiDiv.style.width = "100%";
            aiDiv.style.display = "flex";
            aiDiv.style.flexDirection = "column";

            aiDiv.innerHTML = `
                <div class="thinking-box">
                    <div class="thinking-header" onclick="toggleThink('${thinkingId}')">
                        <span>⚙️ جاري التفكير... (اضغط للتفاصيل)</span>
                    </div>
                    <div id="${thinkingId}" class="thinking-content"></div>
                </div>
                <div class="msg ai-msg" style="margin-top:10px; display:none;"></div>
            `;
            chat.appendChild(aiDiv);
            chat.scrollTop = chat.scrollHeight;

            const contentBox = document.getElementById(thinkingId);

            try {
                const res = await fetch('/stream', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: text})
                });

                const reader = res.body.getReader();
                let fullResponse = "";

                while (true) {
                    const {done, value} = await reader.read();
                    if (done) break;
                    const chunk = new TextDecoder().decode(value);
                    fullResponse += chunk;

                    // تحديث التفكير
                    contentBox.innerText = fullResponse.replace(/```[\s\S]*?```/g, "[كود...]");
                    chat.scrollTop = chat.scrollHeight; // التمرير التلقائي للشات وليس للتفكير
                }

                // انتهى التفكير
                contentBox.previousElementSibling.innerHTML = "<span>✅ اكتملت المعالجة</span>";

                // استخراج الكود
                const codeMatch = fullResponse.match(/```(?:html)?\s*([\s\S]*?)```/);
                const fileMatch = fullResponse.match(/FILENAME:\s*([\w\.\-\_]+)/i);

                if (codeMatch) {
                    const finalCode = codeMatch[1];
                    const filename = fileMatch ? fileMatch[1].trim() : "index.html";

                    // إنشاء كارت التحكم (الحل لمشكلة الأزرار)
                    // نستخدم dataset لتخزين الكود بدلاً من تمريره في الدالة
                    const card = document.createElement('div');
                    card.className = "code-card";
                    card.dataset.code = finalCode; // تخزين الكود هنا بأمان
                    card.dataset.filename = filename;

                    card.innerHTML = `
                        <div class="card-header">
                            <span>ملف: <b>${filename}</b></span>
                        </div>
                        <div class="card-actions">
                            <button class="btn btn-preview" onclick="openPreview(this)">👁️ معاينة</button>
                            <button class="btn btn-publish" onclick="publish(this)">☁️ نشر</button>
                            <button class="btn btn-reject" onclick="reject(this)">❌</button>
                        </div>
                    `;
                    chat.appendChild(card);
                    chat.scrollTop = chat.scrollHeight;
                } else {
                    // إذا كان مجرد رد نصي بدون كود
                    const msgDiv = aiDiv.querySelector('.msg');
                    msgDiv.style.display = "block";
                    msgDiv.innerText = fullResponse;
                }

            } catch (e) {
                chat.innerHTML += `<div class="msg ai-msg" style="color:red">خطأ: ${e.message}</div>`;
            }
        }

        function toggleThink(id) {
            const el = document.getElementById(id);
            el.style.display = el.style.display === "block" ? "none" : "block";
        }

        // دالة المعاينة الجديدة (تأخذ الكود من dataset)
        function openPreview(btn) {
            const card = btn.closest('.code-card');
            const code = card.dataset.code;
            modal.style.display = "flex";
            iframe.srcdoc = code;
        }

        function closePreview() {
            modal.style.display = "none";
            iframe.srcdoc = "";
        }

        // دالة الرفض
        function reject(btn) {
            if(confirm("هل أنت متأكد من حذف هذا المقترح؟")) {
                const card = btn.closest('.code-card');
                const thinking = card.previousElementSibling; // محاولة حذف صندوق التفكير المرتبط
                card.remove();
                if(thinking && thinking.querySelector('.thinking-box')) thinking.remove();
            }
        }

        // دالة النشر الجديدة
        async function publish(btn) {
            const card = btn.closest('.code-card');
            const code = card.dataset.code;
            const filename = card.dataset.filename;

            const originalText = btn.innerHTML;
            btn.innerHTML = "⏳...";
            btn.disabled = true;

            try {
                const res = await fetch('/save', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({filename, code})
                });
                const data = await res.json();

                if (data.success) {
                    btn.innerHTML = "✅ تم!";
                    btn.style.background = "#238636"; // تأكيد أخضر
                    setTimeout(() => { btn.innerHTML = "☁️ نشر"; btn.disabled = false; btn.style.background = "#1f6feb"; }, 3000);
                } else {
                    alert("خطأ: " + data.message);
                    btn.innerHTML = "❌";
                    btn.disabled = false;
                }
            } catch (e) {
                alert("خطأ اتصال");
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
        }

        input.addEventListener('keypress', (e) => { if(e.key === 'Enter') send(); });
    </script>
</body>
</html>
"""

@app.route('/')
def home(): return HTML_PAGE

@app.route('/stream', methods=['POST'])
def stream():
    user_msg = request.json.get("message")

    # قراءة الملفات الحالية
    project_files = ""
    for f in os.listdir('.'):
        if f.endswith(('.html', '.css', '.js', '.py')):
             with open(f, "r") as file: project_files += f"\n--- {f} ---\n{file.read()}\n"

    def generate():
        # تعليمات النظام المحدثة
        gen = client.chat.completions.create(
            model="deepseek-ai/deepseek-v3.2",
            messages=[
                {"role": "system", "content": f"أنت مساعد برمجي. الملفات الحالية:\n{project_files}\nالمطلوب: اشرح خطواتك، ثم اكتب الكود كاملاً داخل ```html (أو اللغة المناسبة). ابدأ الكود بـ FILENAME: name."},
                {"role": "user", "content": user_msg}
            ], stream=True
        )
        for chunk in gen:
            if chunk.choices[0].delta.content: yield chunk.choices[0].delta.content

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/save', methods=['POST'])
def save():
    data = request.json
    try:
        with open(data['filename'], "w", encoding="utf-8") as f: f.write(data['code'])
        # أوامر Git الصامتة
        commands = [
            ["git", "add", "."],
            ["git", "commit", "--allow-empty", "-m", f"AI Update: {data['filename']}"],
            ["git", "pull", "origin", "main", "--rebase"],
            ["git", "push", "origin", "main", "--force"]
        ]
        for cmd in commands: subprocess.run(cmd, check=False)
        return jsonify({"success": True})
    except Exception as e: return jsonify({"success": False, "message": str(e)})

if __name__ == '__main__': app.run(host='0.0.0.0', port=8080)
