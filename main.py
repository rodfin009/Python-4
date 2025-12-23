import os, subprocess, json, shutil
from flask import Flask, Response, stream_with_context, request, jsonify
from models import generate_response, MODELS_CONFIG

app = Flask(__name__)

MODELS_META_JSON = json.dumps({k: v["allowed_params"] for k, v in MODELS_CONFIG.items()})

# دالة تنظيف صارمة جداً لمنع أخطاء IPv6 والرموز المخفية
def get_safe_repo_name(repo_input):
    repo = repo_input.strip()
    # إزالة أي تنسيق Markdown أو روابط كاملة
    repo = repo.replace("https://github.com/", "").replace("http://github.com/", "")
    repo = repo.replace("[github.com]", "").replace("(https://github.com/)", "")
    repo = repo.split('.git')[0].split(' ')[0].strip('/')
    return repo

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Studio Pro</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        :root { --bg: #0d1117; --card: #161b22; --border: #30363d; --accent: #1f6feb; --text: #e6edf3; --user-bubble: #1f6feb; --ai-bubble: #161b22; --success: #238636; }
        * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background: var(--bg); color: var(--text); margin: 0; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }

        .header { background: var(--card); padding: 0 15px; border-bottom: 1px solid var(--border); display: flex; gap: 10px; align-items: center; height: 55px; }
        .model-select { flex: 1; background: var(--bg); border: 1px solid var(--border); color: white; padding: 6px 12px; border-radius: 8px; cursor: pointer; font-size: 13px; outline: none; }
        .header-btn { background: transparent; border: 1px solid var(--border); color: #8b949e; width: 32px; height: 32px; border-radius: 6px; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        .status-dot { width: 6px; height: 6px; border-radius: 50%; background: #8b949e; }
        .status-dot.connected { background: var(--success); box-shadow: 0 0 4px var(--success); }

        #chat { flex: 1; overflow-y: auto; padding: 20px 15px; display: flex; flex-direction: column; gap: 20px; padding-bottom: 100px; }
        .msg-wrapper { display: flex; flex-direction: column; max-width: 85%; }
        .msg-wrapper.user { align-self: flex-start; align-items: flex-start; }
        .msg-wrapper.ai { align-self: flex-end; align-items: flex-end; }
        .model-label { font-size: 10px; color: #8b949e; margin-bottom: 4px; padding: 0 2px; display: flex; align-items: center; gap: 4px; opacity: 0.8; }
        .bubble { padding: 10px 14px; border-radius: 12px; font-size: 14px; line-height: 1.6; position: relative; word-wrap: break-word; width: fit-content; min-width: 50px; }
        .user .bubble { background: var(--user-bubble); color: white; border-bottom-right-radius: 2px; }
        .ai .bubble { background: var(--ai-bubble); border: 1px solid var(--border); border-bottom-left-radius: 2px; }

        .thinking-widget { margin-bottom: 8px; user-select: none; }
        .thinking-toggle { background: rgba(48, 54, 61, 0.4); border: 1px solid rgba(48, 54, 61, 0.8); color: #8b949e; font-size: 11px; padding: 4px 10px; border-radius: 20px; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; width: fit-content; }
        .thinking-details { display: none; margin-top: 6px; padding: 10px; background: #0b0e11; border-radius: 8px; border-right: 2px solid #30363d; font-family: monospace; font-size: 11px; color: #79c0ff; line-height: 1.4; max-height: 200px; overflow-y: auto; }
        .mini-spinner { width: 10px; height: 10px; border: 2px solid #8b949e; border-top-color: transparent; border-radius: 50%; animation: spin 1s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }

        .code-card { margin-top: 10px; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; background: #0d1117; width: 100%; }
        .card-head { background: #21262d; padding: 8px 12px; font-size: 12px; color: #8b949e; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); }
        .card-body { padding: 8px; display: flex; gap: 8px; }
        .btn-act { flex: 1; padding: 8px; border: none; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; color: white; display: flex; align-items: center; justify-content: center; gap: 5px; }
        .btn-view { background: var(--success); }
        .btn-pub { background: var(--accent); }
        .btn-del { background: #da3633; flex: 0.3; }

        .input-bar { position: fixed; bottom: 0; left: 0; right: 0; background: #010409; padding: 12px; border-top: 1px solid var(--border); display: flex; gap: 8px; z-index: 50; }
        #userInput { flex: 1; background: var(--bg); border: 1px solid var(--border); border-radius: 20px; color: white; padding: 10px 15px; outline: none; font-size: 15px; }
        #sendBtn { width: 40px; height: 40px; border-radius: 50%; background: var(--accent); color: white; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 16px; transform: rotate(180deg); }

        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 100; align-items: center; justify-content: center; backdrop-filter: blur(2px); }
        .modal-box { background: var(--card); width: 90%; max-width: 400px; padding: 20px; border-radius: 12px; border: 1px solid var(--border); box-shadow: 0 10px 40px rgba(0,0,0,0.5); max-height: 85vh; overflow-y: auto; }

        .control-group { margin-bottom: 20px; display: none; border-bottom: 1px solid #21262d; padding-bottom: 15px; } 
        .control-group.active { display: block; }
        .setting-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .setting-info { font-size: 14px; color: #e6edf3; font-weight: 500; }
        .setting-sub { font-size: 11px; color: #8b949e; margin-top: 2px; display: block; line-height: 1.3; }
        input[type=range] { width: 100%; accent-color: var(--accent); height: 4px; margin-top: 8px; }
        .switch { position: relative; display: inline-block; width: 40px; height: 22px; }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #30363d; transition: .3s; border-radius: 34px; }
        .slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 3px; bottom: 3px; background-color: #8b949e; transition: .3s; border-radius: 50%; }
        input:checked + .slider { background-color: rgba(35, 134, 54, 0.2); border: 1px solid var(--success); }
        input:checked + .slider:before { transform: translateX(18px); background-color: var(--success); }
        .error-msg { background: rgba(218, 54, 51, 0.1); border: 1px solid #da3633; color: #ff7b72; padding: 12px; border-radius: 6px; font-size: 11px; margin-top: 10px; display: none; text-align: left; direction: ltr; white-space: pre-wrap; font-family: monospace; }

        #previewModal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 150; flex-direction: column; }
        iframe { flex: 1; border: none; background: white; }
    </style>
</head>
<body>

    <div class="header">
        <select id="modelSelect" class="model-select" onchange="updateUI()">
            <option value="deepseek">DeepSeek V3.2</option>
            <option value="moonshot">Kimi K2 Thinking</option>
            <option value="mistral">Mistral Large 3</option>
            <option value="gpt_oss">GPT-OSS 120B</option>
        </select>
        <button class="header-btn" onclick="openModal('settingsModal')"><i class="fas fa-sliders-h"></i></button>
        <button class="header-btn" onclick="openModal('githubModal')"><i class="fab fa-github"></i> <span class="status-dot" id="ghDot"></span></button>
    </div>

    <div id="chat"></div>

    <div class="input-bar">
        <button id="sendBtn" onclick="send()">➤</button>
        <input type="text" id="userInput" placeholder="اكتب رسالتك..." autocomplete="off">
    </div>

    <div id="githubModal" class="modal">
        <div class="modal-box">
            <h3 style="margin-top:0"><i class="fab fa-github"></i> استيراد وربط</h3>
            <div id="ghConnected" style="display:none; text-align:center;">
                <p style="color:var(--success); font-size:14px;">✅ متصل بـ <b id="repoName" style="color:white"></b></p>
                <button onclick="disconnectGH()" style="background:#da3633; color:white; border:none; padding:8px 12px; border-radius:6px; cursor:pointer;">فك الربط</button>
            </div>
            <div id="ghForm">
                <input type="text" id="ghRepo" placeholder="username/repo" style="width:100%; padding:10px; margin-bottom:10px; background:#0d1117; border:1px solid #30363d; color:white; border-radius:6px;">
                <input type="password" id="ghToken" placeholder="Token" style="width:100%; padding:10px; margin-bottom:10px; background:#0d1117; border:1px solid #30363d; color:white; border-radius:6px;">
                <button id="ghConnectBtn" onclick="saveAndCloneGH()" style="width:100%; background:var(--accent); color:white; border:none; padding:10px; border-radius:6px; cursor:pointer;">تحقق واتصال</button>
                <div id="cloneStatus" style="font-size:12px; margin-top:10px; color:#8b949e; display:none;">جاري المزامنة... <i class="fas fa-spinner fa-spin"></i></div>
                <div id="ghError" class="error-msg"></div>
            </div>
            <button onclick="closeModal('githubModal')" style="margin-top:10px; width:100%; background:transparent; border:none; color:#8b949e; cursor:pointer;">إغلاق</button>
        </div>
    </div>

    <div id="settingsModal" class="modal">
        <div class="modal-box">
            <h3 style="margin-top:0; margin-bottom:20px;">⚙️ إعدادات النموذج</h3>
            <div class="control-group active"><div class="setting-row"><div><div class="setting-info">بحث الإنترنت</div><span class="setting-sub">تزويد النموذج بمعلومات حديثة</span></div><label class="switch"><input type="checkbox" id="searchToggle"><span class="slider"></span></label></div></div>
            <div id="grp_ds_think" class="control-group"><div class="setting-row"><div><div class="setting-info">DeepSeek Thinking ⚡</div><span class="setting-sub">تفعيل التفكير العميق</span></div><label class="switch"><input type="checkbox" id="dsThinkToggle" checked><span class="slider"></span></label></div></div>
            <div id="grp_stream" class="control-group"><div class="setting-row"><div><div class="setting-info">Stream Output</div><span class="setting-sub">عرض النص تدريجياً</span></div><label class="switch"><input type="checkbox" id="streamToggle" checked><span class="slider"></span></label></div></div>
            <div id="grp_temp" class="control-group"><div class="setting-info">Temperature <span id="v_temp" style="color:var(--accent)">0.7</span></div><input type="range" id="p_temp" min="0" max="2" step="0.1" oninput="document.getElementById('v_temp').innerText=this.value"></div>
            <div id="grp_top_p" class="control-group"><div class="setting-info">Top P <span id="v_topp" style="color:var(--accent)">0.9</span></div><input type="range" id="p_topp" min="0" max="1" step="0.05" oninput="document.getElementById('v_topp').innerText=this.value"></div>
            <div id="grp_tokens" class="control-group"><div class="setting-info">Max Tokens <span id="v_tok" style="color:var(--accent)">4096</span></div><input type="range" id="p_tokens" min="1024" max="16384" step="1024" oninput="document.getElementById('v_tok').innerText=this.value"></div>
            <button onclick="closeModal('settingsModal')" style="width:100%; background:#30363d; color:white; border:none; padding:12px; border-radius:6px; cursor:pointer; font-weight:bold;">إغلاق</button>
        </div>
    </div>

    <div id="previewModal"><div style="background:#161b22; padding:5px; display:flex; justify-content:flex-end;"><button onclick="closeModal('previewModal')" style="color:#ff7b72; background:none; border:none; font-size:24px;">×</button></div><iframe id="previewFrame"></iframe></div>

    <script>
        const META = __MODELS_META_PLACEHOLDER__;
        let FILE_CACHE = {};

        function updateUI() {
            const m = document.getElementById("modelSelect").value;
            const allow = META[m] || [];
            const show = (id, key) => { const el = document.getElementById(id); if(el) el.classList.toggle("active", allow.includes(key)); };
            show("grp_temp", "temperature"); show("grp_top_p", "top_p"); show("grp_tokens", "max_tokens");
            show("grp_stream", "stream"); show("grp_ds_think", "deepseek_thinking");
            document.getElementById("p_temp").value = 0.7; document.getElementById("v_temp").innerText = "0.7";
        }

        window.onload = () => { checkGH(); updateUI(); };

        async function send() {
            const txt = document.getElementById("userInput").value.trim();
            if(!txt) return;
            document.getElementById("userInput").value = "";
            addMsg(txt, 'user');
            const payload = buildPayload(txt);
            const modelName = document.getElementById("modelSelect").options[document.getElementById("modelSelect").selectedIndex].text;

            const wrapper = document.createElement('div');
            wrapper.className = "msg-wrapper ai";
            wrapper.innerHTML = `<div class="model-label"><i class="fas fa-robot"></i> ${modelName}</div><div class="bubble"><div class="thinking-widget" style="display:none;"><div class="thinking-toggle" onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display==='block'?'none':'block'"><div class="mini-spinner"></div> <span>تفكير...</span></div><div class="thinking-details"></div></div><div class="text-content"></div></div>`;
            document.getElementById('chat').appendChild(wrapper);
            document.getElementById('chat').scrollTop = document.getElementById('chat').scrollHeight;

            const thinkWidget = wrapper.querySelector('.thinking-widget');
            const thinkDetails = wrapper.querySelector('.thinking-details');
            const textContent = wrapper.querySelector('.text-content');
            const statusLabel = wrapper.querySelector('.thinking-toggle span');
            const spinner = wrapper.querySelector('.mini-spinner');

            try {
                const res = await fetch('/stream', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
                const reader = res.body.getReader();
                let fullTxt = "";
                let hasThink = false;

                while(true) {
                    const {done, value} = await reader.read(); if(done) break;
                    const chunk = new TextDecoder().decode(value);
                    if(chunk.includes("__THINK__")) {
                        hasThink = true; thinkWidget.style.display = "block";
                        const parts = chunk.split("__THINK__");
                        for(let i=1; i<parts.length; i++) thinkDetails.innerText += parts[i].split("__TEXT__")[0];
                    }
                    if(chunk.includes("__TEXT__")) {
                        const parts = chunk.split("__TEXT__");
                        for(let i=1; i<parts.length; i++) {
                            const t = parts[i].split("__THINK__")[0];
                            fullTxt += t;
                            textContent.innerText = fullTxt.replace(/```[\s\S]*?```/g, "[كود...]");
                        }
                    }
                    document.getElementById('chat').scrollTop = document.getElementById('chat').scrollHeight;
                }
                spinner.style.display = "none";
                if(hasThink) { statusLabel.innerText = "عرض التفكير"; statusLabel.style.fontSize = "10px"; } 
                else { thinkWidget.style.display = "none"; }

                const codeMatch = fullTxt.match(/```(?:html|css|js|py)?\s*([\s\S]*?)```/);
                const fileMatch = fullTxt.match(/FILENAME:\s*([\w\.\-\_]+)/i);
                if(codeMatch) {
                    const code = codeMatch[1];
                    const filename = fileMatch ? fileMatch[1].trim() : "index.html";
                    const fileId = "file_" + Date.now();
                    FILE_CACHE[fileId] = code;
                    const card = document.createElement('div'); card.className = "code-card";
                    card.innerHTML = `<div class="card-head"><span>${filename}</span></div><div class="card-body"><button class="btn-act btn-view" onclick="openPreview('${fileId}')">معاينة</button><button class="btn-act btn-pub" onclick="pub(this, '${fileId}', '${filename}')">نشر</button><button class="btn-act btn-del" onclick="this.closest('.code-card').remove()">❌</button></div>`;
                    textContent.appendChild(card);
                    document.getElementById('chat').scrollTop = document.getElementById('chat').scrollHeight;
                }
            } catch(e) { textContent.innerText = "Error: " + e.message; }
        }

        function addMsg(txt, type) {
            const d = document.createElement('div'); d.className = "msg-wrapper " + type;
            d.innerHTML = `<div class="bubble">${txt.replace(/</g, "&lt;")}</div>`;
            document.getElementById('chat').appendChild(d);
        }

        function buildPayload(txt) {
            const p = { message: txt, model: document.getElementById("modelSelect").value, search: document.getElementById("searchToggle").checked };
            const getVal = (id) => document.getElementById(id).value;
            const getChk = (id) => document.getElementById(id).checked;
            if(document.getElementById("grp_temp").classList.contains("active")) p.temperature = getVal("p_temp");
            if(document.getElementById("grp_top_p").classList.contains("active")) p.top_p = getVal("p_topp");
            if(document.getElementById("grp_tokens").classList.contains("active")) p.max_tokens = getVal("p_tokens");
            if(document.getElementById("grp_stream").classList.contains("active")) p.stream = getChk("streamToggle");
            if(document.getElementById("grp_ds_think").classList.contains("active")) p.deepseek_thinking = getChk("dsThinkToggle");
            return p;
        }

        function openModal(id){ document.getElementById(id).style.display="flex"; }
        function closeModal(id){ document.getElementById(id).style.display="none"; }

        function openPreview(fileId){ 
            const code = FILE_CACHE[fileId];
            const blob = new Blob([code], {type: 'text/html'});
            document.getElementById("previewModal").style.display="flex"; 
            document.getElementById("previewFrame").src = URL.createObjectURL(blob); 
        }

        function checkGH() {
            const t = localStorage.getItem("ghToken"); const r = localStorage.getItem("ghRepo");
            if(t&&r) { 
                document.getElementById("ghDot").classList.add("connected");
                document.getElementById("ghForm").style.display="none";
                document.getElementById("ghConnected").style.display="block";
                document.getElementById("repoName").innerText = r;
            } else {
                document.getElementById("ghDot").classList.remove("connected");
                document.getElementById("ghForm").style.display="block";
                document.getElementById("ghConnected").style.display="none";
            }
        }

        async function saveAndCloneGH() {
            const repo = document.getElementById("ghRepo").value;
            const token = document.getElementById("ghToken").value;
            const btn = document.getElementById("ghConnectBtn");
            const status = document.getElementById("cloneStatus");
            const errorBox = document.getElementById("ghError");

            if(!repo || !token) { alert("أدخل البيانات"); return; }
            btn.disabled = true; status.style.display = "block"; errorBox.style.display = "none";

            try {
                const res = await fetch('/clone', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({gh_repo: repo, gh_token: token}) });
                const data = await res.json();
                if(data.success) {
                    localStorage.setItem("ghToken", token); localStorage.setItem("ghRepo", repo);
                    checkGH(); closeModal('githubModal');
                } else {
                    errorBox.innerText = data.message; errorBox.style.display = "block";
                }
            } catch(e) { errorBox.innerText = e.message; errorBox.style.display = "block"; }
            btn.disabled = false; status.style.display = "none";
        }

        function disconnectGH(){ localStorage.clear(); checkGH(); }

        async function pub(btn, fileId, filename) {
            const t=localStorage.getItem("ghToken"); const r=localStorage.getItem("ghRepo");
            if(!t) { openModal('githubModal'); return; }
            btn.innerText="..."; 
            try {
                const res = await fetch('/save', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({filename, code:FILE_CACHE[fileId], gh_token:t, gh_repo:r})});
                const data = await res.json();
                if(data.success) { btn.innerText="تم ✅"; btn.style.background="#238636"; }
                else { alert(data.message); btn.innerText="فشل"; }
            } catch(e) { alert(e.message); }
        }
        document.getElementById("userInput").addEventListener("keypress", (e)=>{if(e.key==="Enter") send()});
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return HTML_TEMPLATE.replace("__MODELS_META_PLACEHOLDER__", MODELS_META_JSON)

@app.route('/stream', methods=['POST'])
def stream():
    data = request.json
    try:
        project_context = "Current Project Files Contents:\n"
        # قراءة آمنة للملفات النصية فقط
        allowed_exts = ('.html', '.css', '.js', '.py', '.json', '.md', '.txt')
        for filename in os.listdir('.'):
            if filename.endswith(allowed_exts) and not filename.startswith('.'):
                try:
                    with open(filename, 'r', encoding='utf-8') as f:
                        project_context += f"\nFILE: {filename}\n```\n{f.read()}\n```\n"
                except: pass

        messages = [
            {"role": "system", "content": f"You are a professional coding assistant with access to these files:\n{project_context}\nAlways provide the FULL code in triple backticks. Start the block with FILENAME: <name>."},
            {"role": "user", "content": data.get("message")}
        ]
        return Response(stream_with_context(generate_response(data.get("model"), messages, data, data.get("search"))), mimetype='text/event-stream')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/save', methods=['POST'])
def save():
    d = request.json
    try:
        with open(d['filename'], "w", encoding="utf-8") as f: f.write(d['code'])
        repo = get_safe_repo_name(d['gh_repo'])
        # استخدام صيغة x-access-token وهي الأكثر استقراراً في Git
        remote_url = f"https://x-access-token:{d['gh_token']}@github.com/{repo}.git"

        subprocess.run(["git", "remote", "remove", "origin"], check=False)
        subprocess.run(["git", "remote", "add", "origin", remote_url], check=True)
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "--allow-empty", "-m", "AI Update"], check=True)

        res = subprocess.run(["git", "push", "origin", "main", "--force"], capture_output=True, text=True)
        if res.returncode != 0:
            # محاولة مع فرع master إذا فشل main
            res = subprocess.run(["git", "push", "origin", "master", "--force"], capture_output=True, text=True)

        if res.returncode != 0: return jsonify({"success": False, "message": res.stderr})
        return jsonify({"success": True})
    except Exception as e: return jsonify({"success": False, "message": str(e)})

@app.route('/clone', methods=['POST'])
def clone():
    d = request.json
    repo_name = get_safe_repo_name(d['gh_repo'])
    token = d.get('gh_token').strip()
    remote_url = f"https://x-access-token:{token}@github.com/{repo_name}.git"

    try:
        # تنظيف جذري لضمان عدم وجود ملفات git تالفة
        if os.path.exists(".git"): shutil.rmtree(".git")

        subprocess.run(["git", "init"], check=True)
        subprocess.run(["git", "config", "user.email", "ai@agent.com"], check=True)
        subprocess.run(["git", "config", "user.name", "AI Agent"], check=True)
        subprocess.run(["git", "remote", "add", "origin", remote_url], check=True)

        # اختبار الاتصال الفعلي
        test = subprocess.run(["git", "ls-remote", "origin"], capture_output=True, text=True)
        if test.returncode != 0:
            return jsonify({"success": False, "message": "❌ التوكن أو المستودع خطأ."})

        # جلب الملفات
        subprocess.run(["git", "fetch", "origin"], check=True)
        # محاولة سحب الفرع الرئيسي
        res = subprocess.run(["git", "pull", "origin", "main", "--allow-unrelated-histories"], capture_output=True)
        if res.returncode != 0:
            subprocess.run(["git", "pull", "origin", "master", "--allow-unrelated-histories"], check=True)

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
