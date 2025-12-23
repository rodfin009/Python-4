import os, subprocess
from flask import Flask, Response, stream_with_context, request, jsonify
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=os.environ.get("NVIDIA_API_KEY"))

HTML_PAGE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Coding Agent</title>
    <style>
        * { box-sizing: border-box; }
        body { background: #0d1117; color: #e6edf3; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }

        /* منطقة الشات */
        #chat { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 15px; scroll-behavior: smooth; padding-bottom: 80px; }

        /* الرسائل */
        .msg { padding: 12px 16px; border-radius: 12px; max-width: 85%; line-height: 1.6; font-size: 15px; position: relative; word-wrap: break-word; }
        .user-msg { background: #1f6feb; color: white; align-self: flex-start; border-bottom-right-radius: 2px; }
        .ai-msg { background: #161b22; border: 1px solid #30363d; align-self: flex-end; border-bottom-left-radius: 2px; width: 100%; }

        /* كارت التحكم بالكود */
        .code-card { background: #010409; border: 1px solid #30363d; border-radius: 8px; padding: 12px; margin-top: 10px; display: flex; flex-direction: column; gap: 10px; }
        .card-header { font-size: 13px; color: #8b949e; display: flex; justify-content: space-between; align-items: center; }
        .actions { display: flex; gap: 8px; margin-top: 5px; }

        /* الأزرار داخل الكارت */
        .btn { flex: 1; padding: 10px; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 14px; display: flex; align-items: center; justify-content: center; gap: 5px; transition: 0.2s; }
        .btn-preview { background: #30363d; color: #58a6ff; }
        .btn-publish { background: #238636; color: white; }
        .btn-reject { background: #da3633; color: white; }
        .btn:active { transform: scale(0.96); opacity: 0.8; }

        /* منطقة الإدخال السفلية */
        .input-area { position: fixed; bottom: 0; left: 0; right: 0; background: #161b22; padding: 12px; display: flex; align-items: center; gap: 10px; border-top: 1px solid #30363d; z-index: 10; }
        input { flex: 1; padding: 12px 15px; border-radius: 20px; border: 1px solid #30363d; background: #0d1117; color: white; outline: none; font-size: 16px; }
        .send-btn { width: 45px; height: 45px; border-radius: 50%; border: none; background: #1f6feb; color: white; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; transform: rotate(180deg); /* تدوير السهم ليتناسب مع العربية */ }

        /* نافذة المعاينة المنبثقة */
        #previewModal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 100; flex-direction: column; }
        #previewFrame { flex: 1; background: white; border: none; width: 100%; }
        .modal-header { padding: 10px; background: #161b22; display: flex; justify-content: space-between; align-items: center; color: white; }
        .close-btn { background: none; border: none; color: #ff7b72; font-size: 24px; cursor: pointer; padding: 0 15px; }
    </style>
</head>
<body>
    <div id="chat">
        <div class="msg ai-msg">مرحباً! أنا جاهز لتطوير موقعك. اطلب أي تعديل وسأقوم بتجهيزه لك. 🚀</div>
    </div>

    <div class="input-area">
        <button id="sendBtn" class="send-btn">➤</button>
        <input type="text" id="userInput" placeholder="اكتب طلبك هنا..." autocomplete="off">
    </div>

    <div id="previewModal">
        <div class="modal-header">
            <span>معاينة حية</span>
            <button class="close-btn" onclick="closePreview()">×</button>
        </div>
        <iframe id="previewFrame"></iframe>
    </div>

    <script>
        const chat = document.getElementById('chat');
        const input = document.getElementById('userInput');
        const sendBtn = document.getElementById('sendBtn');
        const previewModal = document.getElementById('previewModal');
        const previewFrame = document.getElementById('previewFrame');

        // إرسال الرسالة
        async function sendMessage() {
            const text = input.value.trim();
            if (!text) return;

            // إضافة رسالة المستخدم
            input.value = "";
            chat.innerHTML += `<div class="msg user-msg">${text}</div>`;
            chat.scrollTop = chat.scrollHeight;

            // إضافة رسالة المساعد (انتظار)
            const aiDiv = document.createElement('div');
            aiDiv.className = "msg ai-msg";
            aiDiv.innerHTML = "⏳ جاري العمل...";
            chat.appendChild(aiDiv);
            chat.scrollTop = chat.scrollHeight;

            try {
                const res = await fetch('/stream', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: text})
                });

                const reader = res.body.getReader();
                let fullText = "";
                aiDiv.innerHTML = ""; // مسح الانتظار

                while (true) {
                    const {done, value} = await reader.read();
                    if (done) break;
                    fullText += new TextDecoder().decode(value);
                    aiDiv.innerHTML = fullText.replace(/```[\s\S]*?```/g, "<i>(تم توليد كود.. اضغط معاينة لرؤيته)</i>"); // إخفاء الكود الخام
                    chat.scrollTop = chat.scrollHeight;
                }

                // الكشف عن الكود وإنشاء الكارت
                const codeMatch = fullText.match(/```(?:html)?\s*([\s\S]*?)```/);
                const fileMatch = fullText.match(/FILENAME:\s*([\w\.\-\_]+)/i);

                if (codeMatch) {
                    const code = codeMatch[1];
                    const filename = fileMatch ? fileMatch[1].trim() : "index.html";

                    // استبدال النص بـ "كارت التحكم"
                    aiDiv.innerHTML = ""; 
                    const card = document.createElement('div');
                    card.className = "code-card";
                    card.innerHTML = `
                        <div class="card-header">
                            <span>📄 مقترح لملف: <b>${filename}</b></span>
                        </div>
                        <div class="actions">
                            <button class="btn btn-preview" onclick="showPreview(this)">👁️ معاينة</button>
                            <button class="btn btn-publish" onclick="publish(this, '${filename}')">✅ نشر</button>
                            <button class="btn btn-reject" onclick="reject(this)">❌ إلغاء</button>
                        </div>
                    `;
                    // تخزين الكود في عنصر مخفي داخل الكارت لاستخدامه لاحقاً
                    card.dataset.code = code;
                    aiDiv.appendChild(card);
                    chat.scrollTop = chat.scrollHeight;
                }

            } catch (e) {
                aiDiv.innerHTML = `<span style="color:#ff7b72">❌ حدث خطأ: ${e.message}</span>`;
            }
        }

        // وظائف الأزرار
        sendBtn.onclick = sendMessage;
        input.onkeypress = (e) => { if(e.key === 'Enter') sendMessage(); };

        function showPreview(btn) {
            const code = btn.closest('.code-card').dataset.code;
            const blob = new Blob([code], {type: 'text/html'});
            previewFrame.src = URL.createObjectURL(blob);
            previewModal.style.display = "flex";
        }

        function closePreview() {
            previewModal.style.display = "none";
            previewFrame.src = "";
        }

        function reject(btn) {
            const msgDiv = btn.closest('.msg');
            msgDiv.innerHTML = "<span style='color:#8b949e;'>❌ تم إلغاء هذا التعديل.</span>";
        }

        async function publish(btn, filename) {
            const code = btn.closest('.code-card').dataset.code;
            btn.innerHTML = "⏳ جاري الرفع...";
            btn.disabled = true;

            try {
                const res = await fetch('/save', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({filename, code})
                });
                const data = await res.json();

                if (data.success) {
                    btn.closest('.code-card').innerHTML = `<div style="color:#238636; text-align:center;">✅ <b>تم النشر بنجاح!</b><br>الموقع يعمل الآن على GitHub</div>`;
                } else {
                    btn.innerHTML = "❌ فشل";
                    alert("خطأ: " + data.message);
                    btn.disabled = false;
                }
            } catch (e) {
                btn.innerHTML = "❌ خطأ";
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home(): return HTML_PAGE

@app.route('/stream', methods=['POST'])
def stream():
    try:
        user_msg = request.json.get("message")

        # قراءة سياق الملفات
        files_context = ""
        for f in os.listdir('.'):
            if f.endswith(('.html', '.css', '.js')):
                with open(f, "r") as file: files_context += f"\n--- {f} ---\n{file.read()}\n"

        def generate():
            gen = client.chat.completions.create(
                model="deepseek-ai/deepseek-v3.2",
                messages=[
                    {"role": "system", "content": f"أنت خبير تطوير ويب. الملفات الحالية:\n{files_context}\nعند الطلب، أرسل الكود كاملاً داخل ```html واذكر FILENAME: اسم_الملف."},
                    {"role": "user", "content": user_msg}
                ], stream=True
            )
            for chunk in gen:
                if chunk.choices[0].delta.content: yield chunk.choices[0].delta.content
        return Response(stream_with_context(generate()), mimetype='text/event-stream')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/save', methods=['POST'])
def save():
    data = request.json
    try:
        with open(data['filename'], "w") as f: f.write(data['code'])
        # الرفع التلقائي
        subprocess.run(["git", "add", "."], check=False)
        subprocess.run(["git", "commit", "-m", "AI Update"], check=False)
        subprocess.run(["git", "pull", "origin", "main", "--rebase"], check=False)
        subprocess.run(["git", "push", "origin", "main", "--force"], check=False)
        return jsonify({"success": True})
    except Exception as e: return jsonify({"success": False, "message": str(e)})

if __name__ == '__main__': app.run(host='0.0.0.0', port=8080)
