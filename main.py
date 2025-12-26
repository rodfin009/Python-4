import os, subprocess, json, shutil, time
from flask import Flask, Response, stream_with_context, request, jsonify
from models import generate_response, MODELS_CONFIG

app = Flask(__name__)

MODELS_META_JSON = json.dumps({k: v["allowed_params"] for k, v in MODELS_CONFIG.items()})

def get_safe_repo_name(repo_input):
    repo = repo_input.strip()
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
        :root { --bg: #0d1117; --card: #161b22; --border: #30363d; --accent: #1f6feb; --text: #e6edf3; --user-bubble: #1f6feb; --ai-bubble: #161b22; --success: #238636; --danger: #da3633; }
        * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background: var(--bg); color: var(--text); margin: 0; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }

        .header { background: var(--card); padding: 0 15px; border-bottom: 1px solid var(--border); display: flex; gap: 10px; align-items: center; height: 55px; z-index: 100; }
        .model-select { flex: 1; background: var(--bg); border: 1px solid var(--border); color: white; padding: 6px 12px; border-radius: 8px; cursor: pointer; font-size: 13px; outline: none; }
        .header-btn { background: transparent; border: 1px solid var(--border); color: #8b949e; width: 32px; height: 32px; border-radius: 6px; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        .status-dot { width: 6px; height: 6px; border-radius: 50%; background: #8b949e; }
        .status-dot.connected { background: var(--success); box-shadow: 0 0 4px var(--success); }

        #chat { flex: 1; overflow-y: auto; padding: 20px 15px; display: flex; flex-direction: column; gap: 20px; padding-bottom: 120px; scroll-behavior: smooth; }
        .msg-wrapper { display: flex; flex-direction: column; max-width: 90%; width: 100%; }
        .msg-wrapper.user { align-self: flex-start; align-items: flex-start; }
        .msg-wrapper.ai { align-self: flex-end; align-items: flex-end; }

        .bubble { padding: 12px 16px; border-radius: 12px; font-size: 14px; line-height: 1.6; position: relative; word-wrap: break-word; }
        .user .bubble { background: var(--user-bubble); color: white; border-bottom-right-radius: 2px; max-width: 85%; }
        .ai .bubble { background: var(--ai-bubble); border: 1px solid var(--border); border-bottom-left-radius: 2px; width: 100%; }

        .model-label { font-size: 11px; color: #8b949e; margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }

        .thinking-widget { margin-bottom: 10px; width: 100%; }
        .thinking-toggle { 
            background: rgba(48, 54, 61, 0.4); border: 1px solid var(--border); color: #8b949e; 
            font-size: 11px; padding: 5px 12px; border-radius: 20px; cursor: pointer; 
            display: inline-flex; align-items: center; gap: 8px; user-select: none; transition: 0.2s;
        }
        .thinking-details { 
            display: none; margin-top: 8px; padding: 15px; background: #0b0e11; border-radius: 8px; 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            font-size: 12px; color: #79c0ff; border-right: 2px solid var(--accent); 
            max-height: 300px; overflow-y: auto; direction: rtl; text-align: right; 
            white-space: pre-wrap; line-height: 1.8;
        }

        .action-line {
            display: flex; align-items: center; gap: 10px; 
            background: rgba(255,255,255,0.03); padding: 8px 12px; 
            border-radius: 6px; margin: 8px 0; border: 1px solid #30363d;
            font-family: monospace; direction: ltr;
            justify-content: flex-end; 
        }
        .action-text { color: #e6edf3; font-size: 12px; margin-right: auto; }
        .action-status { display: flex; align-items: center; }
        .action-spinner { 
            width: 14px; height: 14px; border: 2px solid #8b949e; 
            border-top-color: transparent; border-radius: 50%; 
            animation: spin 1s linear infinite; 
        }
        .action-check { color: var(--success); font-size: 14px; display: none; }

        .action-line.done { border-color: var(--success); background: rgba(35, 134, 54, 0.1); }
        .action-line.done .action-spinner { display: none; }
        .action-line.done .action-check { display: block; }

        .rich-text { white-space: pre-wrap; margin-bottom: 10px; direction: rtl; text-align: right; }
        .code-box { margin-top: 12px; border: 1px solid var(--border); border-radius: 10px; overflow: hidden; background: #0b0e11; width: 100%; direction: ltr; text-align: left; }
        .code-box-head { background: #21262d; padding: 8px 12px; font-size: 12px; color: #8b949e; display: flex; justify-content: space-between; align-items: center; }
        .code-area { width: 100%; border: none; outline: none; resize: vertical; min-height: 150px; background: #0d1117; color: #e6edf3; font-family: monospace; font-size: 12px; padding: 12px; direction: ltr; }
        .code-actions { padding: 8px; display: flex; gap: 8px; background: #161b22; border-top: 1px solid var(--border); flex-wrap: wrap; }
        .act-btn { flex: 1; padding: 8px; border: none; border-radius: 8px; cursor: pointer; color: white; font-size: 12px; display: flex; align-items: center; justify-content: center; gap: 6px; min-width: 80px; }
        .act-view { background: var(--success); }
        .act-pub { background: var(--accent); }
        .act-copy { background: #30363d; }
        .act-reject { background: var(--danger); }

        .mini-spinner { width: 10px; height: 10px; border: 2px solid #8b949e; border-top-color: transparent; border-radius: 50%; animation: spin 1s linear infinite; }
        .check-icon { display: none; color: var(--success); font-size: 12px; }
        @keyframes spin { to { transform: rotate(360deg); } }

        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 100; align-items: center; justify-content: center; backdrop-filter: blur(2px); }
        .modal-box { background: var(--card); width: 90%; max-width: 400px; padding: 20px; border-radius: 12px; border: 1px solid var(--border); max-height: 85vh; overflow-y: auto; }
        .input-bar { position: fixed; bottom: 0; left: 0; right: 0; background: #010409; padding: 12px; border-top: 1px solid var(--border); display: flex; gap: 8px; z-index: 50; }
        #userInput { flex: 1; background: var(--bg); border: 1px solid var(--border); border-radius: 20px; color: white; padding: 10px 15px; outline: none; font-size: 15px; text-align: right; }
        #sendBtn { width: 40px; height: 40px; border-radius: 50%; background: var(--accent); color: white; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; }

        .control-group { margin-bottom: 20px; display: none; border-bottom: 1px solid #21262d; padding-bottom: 15px; }
        .control-group.active { display: block; }
        .setting-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px; }
        .setting-info { font-size: 14px; color: #e6edf3; font-weight: 500; }
        .setting-sub { font-size: 11px; color: #8b949e; display: block; line-height: 1.3; margin-top: 4px; margin-bottom: 8px; }
        input[type=range] { width: 100%; accent-color: var(--accent); height: 4px; }
        .switch { position: relative; display: inline-block; width: 40px; height: 22px; }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #30363d; transition: .3s; border-radius: 34px; }
        .slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 3px; bottom: 3px; background-color: #8b949e; transition: .3s; border-radius: 50%; }
        input:checked + .slider { background-color: rgba(35, 134, 54, 0.2); border: 1px solid var(--success); }
        input:checked + .slider:before { transform: translateX(18px); background-color: var(--success); }

        #previewModal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 150; flex-direction: column; }
        .preview-header { background: #161b22; padding: 10px; display: flex; justify-content: space-between; align-items: center; color: white; border-bottom: 1px solid var(--border); }
        iframe { flex: 1; border: none; background: white; width: 100%; height: 100%; }
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
        <input type="text" id="userInput" placeholder="اكتب رسالتك..." autocomplete="off">
        <button id="sendBtn" onclick="send()">➤</button>
    </div>

    <div id="githubModal" class="modal">
        <div class="modal-box">
            <h3><i class="fab fa-github"></i> استيراد وربط</h3>
            <div id="ghConnected" style="display:none; text-align:center;">
                <p style="color:var(--success); font-size:14px;">✅ متصل بـ <b id="repoName" style="color:white"></b></p>
                <button onclick="disconnectGH()" style="background:#da3633; color:white; border:none; padding:8px 12px; border-radius:6px; cursor:pointer;">فك الربط</button>
            </div>
            <div id="ghForm">
                <input type="text" id="ghRepo" placeholder="username/repo" style="width:100%; padding:10px; margin-bottom:10px; background:#0d1117; border:1px solid #30363d; color:white; border-radius:6px;">
                <input type="password" id="ghToken" placeholder="Token" style="width:100%; padding:10px; margin-bottom:10px; background:#0d1117; border:1px solid #30363d; color:white; border-radius:6px;">
                <button id="ghConnectBtn" onclick="saveAndCloneGH()" style="width:100%; background:var(--accent); color:white; border:none; padding:10px; border-radius:6px; cursor:pointer;">تحقق واتصال</button>
            </div>
            <button onclick="closeModal('githubModal')" style="margin-top:10px; width:100%; background:transparent; border:none; color:#8b949e; cursor:pointer;">إغلاق</button>
        </div>
    </div>

    <div id="settingsModal" class="modal">
        <div class="modal-box">
            <h3>⚙️ إعدادات النموذج</h3>
            <div class="control-group active"><div class="setting-row"><div><div class="setting-info">بحث الإنترنت</div></div><label class="switch"><input type="checkbox" id="searchToggle"><span class="slider"></span></label></div><span class="setting-sub">السماح للنموذج بالوصول للويب.</span></div>
            <div id="grp_ds_think" class="control-group"><div class="setting-row"><div><div class="setting-info">DeepSeek Thinking ⚡</div></div><label class="switch"><input type="checkbox" id="dsThinkToggle" checked><span class="slider"></span></label></div></div>
            <div id="grp_stream" class="control-group"><div class="setting-row"><div><div class="setting-info">Stream Output</div></div><label class="switch"><input type="checkbox" id="streamToggle" checked><span class="slider"></span></label></div></div>
            <div id="grp_temp" class="control-group"><div class="setting-row"><div class="setting-info">Temperature <span id="v_temp" style="color:var(--accent)">0.7</span></div></div><input type="range" id="p_temp" min="0" max="2" step="0.1" oninput="document.getElementById('v_temp').innerText=this.value"></div>
            <div id="grp_top_p" class="control-group"><div class="setting-row"><div class="setting-info">Top P <span id="v_topp" style="color:var(--accent)">0.9</span></div></div><input type="range" id="p_topp" min="0" max="1" step="0.05" oninput="document.getElementById('v_topp').innerText=this.value"></div>
            <div id="grp_tokens" class="control-group"><div class="setting-row"><div class="setting-info">Max Tokens <span id="v_tok" style="color:var(--accent)">4096</span></div></div><input type="range" id="p_tokens" min="1024" max="16384" step="1024" oninput="document.getElementById('v_tok').innerText=this.value"></div>
            <button onclick="closeModal('settingsModal')" style="width:100%; background:#30363d; color:white; border:none; padding:12px; border-radius:6px; cursor:pointer; font-weight:bold;">إغلاق</button>
        </div>
    </div>

    <div id="previewModal">
        <div class="preview-header">
            <span id="previewTitle" style="font-size:14px; font-weight:bold;">معاينة</span>
            <button onclick="closeModal('previewModal')" style="color:#ff7b72; background:none; border:none; font-size:24px; cursor:pointer;">×</button>
        </div>
        <iframe id="previewFrame"></iframe>
    </div>

    <script>
        const META = __MODELS_META_PLACEHOLDER__;
        let FILE_CACHE = {};

        function openModal(id){ document.getElementById(id).style.display="flex"; }
        function closeModal(id){ document.getElementById(id).style.display="none"; }

        function updateUI() {
            const m = document.getElementById("modelSelect").value;
            const allow = META[m] || [];
            const show = (id, key) => { const el = document.getElementById(id); if(el) el.classList.toggle("active", allow.includes(key)); };
            show("grp_temp", "temperature"); show("grp_top_p", "top_p"); show("grp_tokens", "max_tokens");
            show("grp_stream", "stream"); show("grp_ds_think", "deepseek_thinking");
        }

        function extractBlocks(txt) {
            const blocks = [];
            const re = /```(\w*)\s*([\s\S]*?)```/g;
            let m;
            while((m=re.exec(txt))!==null) {
                let lang = m[1].trim().toLowerCase();
                let code = m[2];
                if (!lang) {
                    if (code.includes("<!DOCTYPE html") || code.includes("<html")) lang = "html";
                    else if (code.includes("import ") || code.includes("def ")) lang = "python";
                    else lang = "txt";
                }
                blocks.push({ lang: lang, code: code });
            }
            return blocks;
        }

        function extractName(code, lang, index) {
            const nameMatch = code.match(/(?:FILENAME|File|ملف):\s*([a-zA-Z0-9_.-]+)/i);
            if (nameMatch) return nameMatch[1].trim();
            if (lang === 'html') return 'index.html';
            if (lang === 'css') return 'style.css';
            if (lang === 'js' || lang === 'javascript') return 'script.js';
            if (lang === 'py') return 'main.py';
            return `file_${index+1}.txt`;
        }

        function updateLive(raw, textEl, codeWrap, codeArea, badge) {
            const parts = raw.split(/```/);
            if(parts.length % 2 === 0) {
                textEl.innerText = parts.slice(0, -1).join("").replace(/```/g, "");
                codeWrap.style.display = "block";
                let currentCode = parts[parts.length-1];
                currentCode = currentCode.replace(/^[a-zA-Z0-9]+\n/, "");
                codeArea.value = currentCode;
                badge.innerText = "جاري الكتابة...";
            } else {
                textEl.innerText = raw.replace(/```[\s\S]*?```/g, " [كود مكتمل] ");
                codeWrap.style.display = "none";
            }
        }

        async function send() {
            const input = document.getElementById("userInput");
            const txt = input.value.trim();
            if(!txt) return;
            input.value = "";

            const uDiv = document.createElement('div');
            uDiv.className = "msg-wrapper user";
            uDiv.innerHTML = `<div class="bubble">${txt.replace(/</g, "&lt;")}</div>`;
            document.getElementById('chat').appendChild(uDiv);

            const aiDiv = document.createElement('div');
            aiDiv.className = "msg-wrapper ai";
            const modelName = document.getElementById("modelSelect").options[document.getElementById("modelSelect").selectedIndex].text;

            aiDiv.innerHTML = `
                <div class="model-label"><i class="fas fa-robot"></i> ${modelName}</div>
                <div class="bubble">
                    <div class="thinking-widget" style="display:none">
                        <div class="thinking-toggle" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='block'?'none':'block'">
                            <div class="mini-spinner"></div> 
                            <i class="fas fa-check check-icon"></i>
                            <span id="thinkLabel">جاري التفكير...</span>
                        </div>
                        <div class="thinking-details"></div>
                    </div>
                    <div class="rich-text"></div>
                    <div class="code-box live-box" style="display:none">
                        <div class="code-box-head"><span>الكود المباشر</span><span class="badge">LIVE</span></div>
                        <textarea class="code-area" readonly></textarea>
                    </div>
                    <div class="final-cards"></div>
                </div>
            `;
            document.getElementById('chat').appendChild(aiDiv);
            const chat = document.getElementById('chat');
            chat.scrollTop = chat.scrollHeight;

            const textEl = aiDiv.querySelector('.rich-text');
            const liveBox = aiDiv.querySelector('.live-box');
            const liveArea = aiDiv.querySelector('.code-area');
            const liveBadge = aiDiv.querySelector('.badge');
            const thinkWidget = aiDiv.querySelector('.thinking-widget');
            const thinkDetails = aiDiv.querySelector('.thinking-details');
            const thinkLabel = aiDiv.querySelector('#thinkLabel');
            const spinner = aiDiv.querySelector('.mini-spinner');
            const checkIcon = aiDiv.querySelector('.check-icon');
            const cards = aiDiv.querySelector('.final-cards');

            const payload = { 
                message: txt, 
                model: document.getElementById("modelSelect").value,
                search: document.getElementById("searchToggle").checked,
                temperature: document.getElementById("p_temp").value,
                top_p: document.getElementById("p_topp").value,
                max_tokens: document.getElementById("p_tokens").value,
                deepseek_thinking: document.getElementById("dsThinkToggle").checked
            };

            try {
                const res = await fetch('/stream', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const reader = res.body.getReader();
                let buffer = "";
                let fullText = "";
                let state = "IDLE"; 
                let currentActionLine = null;

                while(true) {
                    const {done, value} = await reader.read();
                    if(done) break;
                    buffer += new TextDecoder().decode(value);

                    while (true) {
                        const markers = ["__THINK__", "__TEXT__", "__ACTION__ START:", "__ACTION__ END", "__ACTION__ ERROR"];
                        let match = null;
                        let minIdx = Infinity;

                        for (const m of markers) {
                            const idx = buffer.indexOf(m);
                            if (idx !== -1 && idx < minIdx) {
                                minIdx = idx;
                                match = m;
                            }
                        }

                        if (match === null) break; 

                        const preContent = buffer.substring(0, minIdx);
                        if (preContent) {
                            if (state === "THINKING") {
                                thinkDetails.innerHTML += preContent.replace(/\n/g, "<br>");
                            } else if (state === "TEXT") {
                                fullText += preContent;
                                updateLive(fullText, textEl, liveBox, liveArea, liveBadge);
                            }
                        }

                        buffer = buffer.substring(minIdx + match.length);

                        if (match === "__THINK__") {
                            state = "THINKING";
                            thinkWidget.style.display = "block";
                            thinkDetails.style.display = "block";
                            spinner.style.display = "block";
                            checkIcon.style.display = "none";
                            thinkLabel.innerText = "جاري التفكير...";
                            thinkLabel.style.color = "#8b949e";
                        } 
                        else if (match === "__TEXT__") {
                            state = "TEXT";
                            spinner.style.display = "none";
                            checkIcon.style.display = "inline-block";
                            thinkLabel.innerText = "اكتمل التفكير";
                            thinkLabel.style.color = "#238636";
                            thinkDetails.style.display = "none";
                        }
                        else if (match === "__ACTION__ START:") {
                            state = "ACTION"; 
                            const line = document.createElement('div');
                            line.className = "action-line";
                            line.innerHTML = `<span class="action-text">جاري قراءة: ...</span><div class="action-status"><div class="action-spinner"></div><i class="fas fa-check action-check"></i></div>`;
                            thinkDetails.appendChild(line);
                            currentActionLine = line;
                        }
                        else if (match === "__ACTION__ END" || match === "__ACTION__ ERROR") {
                            if (currentActionLine && preContent) {
                                const span = currentActionLine.querySelector('.action-text');
                                span.innerText = "تم قراءة: " + preContent.trim();
                            }
                            if (currentActionLine) {
                                currentActionLine.classList.add("done");
                                currentActionLine = null;
                            }
                            state = "THINKING"; 
                        }
                    }
                    chat.scrollTop = chat.scrollHeight;
                }

                if (buffer) {
                    if (state === "THINKING") thinkDetails.innerHTML += buffer.replace(/\n/g, "<br>");
                    else if (state === "TEXT") { fullText += buffer; updateLive(fullText, textEl, liveBox, liveArea, liveBadge); }
                }

                spinner.style.display = "none";
                if (state === "TEXT") {
                    checkIcon.style.display = "inline-block";
                    thinkLabel.innerText = "اكتمل التفكير";
                    thinkLabel.style.color = "#238636";
                }
                liveBox.style.display = "none";

                const blocks = extractBlocks(fullText);
                textEl.innerText = fullText.replace(/```[\s\S]*?```/g, "").replace(/FILENAME:.*?\n/gi, "").trim();

                blocks.forEach((b, i) => {
                    const fname = extractName(b.code, b.lang, i);
                    const id = "f_" + Date.now() + "_" + i;
                    FILE_CACHE[id] = { code: b.code, name: fname, lang: b.lang };
                    const isHtml = (b.lang === 'html' || b.code.trim().startsWith('<!DOCTYPE html') || b.code.includes('<html'));
                    const viewBtn = isHtml ? `<button class="act-btn act-view" onclick="openPreview('${id}')"><i class="fa-regular fa-eye"></i> معاينة</button>` : '';
                    const card = document.createElement('div');
                    card.className = "code-box";
                    card.innerHTML = `
                        <div class="code-box-head"><span><i class="fa-regular fa-file-code"></i> ${fname}</span><span class="badge">${b.lang.toUpperCase()}</span></div>
                        <textarea class="code-area" readonly spellcheck="false">${b.code}</textarea>
                        <div class="code-actions">
                            <button class="act-btn act-copy" onclick="copyCode('${id}', this)"><i class="fa-regular fa-copy"></i> نسخ</button>
                            ${viewBtn}
                            <button class="act-btn act-pub" onclick="publishFile('${id}', this)"><i class="fa-brands fa-github"></i> نشر</button>
                            <button class="act-btn act-reject" onclick="deleteMsg(this)"><i class="fa-solid fa-trash"></i> رفض</button>
                        </div>
                    `;
                    cards.appendChild(card);
                });

            } catch(e) { textEl.innerText += "\n[خطأ: " + e.message + "]"; spinner.style.display = "none"; }
        }

        function copyCode(id, btn) {
            navigator.clipboard.writeText(FILE_CACHE[id].code);
            const old = btn.innerHTML; btn.innerHTML = "تم ✅"; setTimeout(() => btn.innerHTML = old, 1500);
        }

        function openPreview(id) {
            const item = FILE_CACHE[id];
            const frame = document.getElementById("previewFrame");
            document.getElementById("previewTitle").innerText = "معاينة: " + item.name;
            document.getElementById("previewModal").style.display = "flex";
            let content = item.code;
            if(item.lang === 'html' || content.includes('<!DOCTYPE html') || content.includes('<html')) {
                frame.srcdoc = content;
            } else {
                frame.srcdoc = `<html><body style="font-family:monospace; padding:20px; white-space:pre-wrap;">${content.replace(/</g, "&lt;")}</body></html>`;
            }
        }

        function deleteMsg(btn) { if(confirm("حذف؟")) btn.closest('.msg-wrapper').remove(); }

        async function publishFile(id, btn) {
            const t = localStorage.getItem("ghToken"), r = localStorage.getItem("ghRepo");
            if(!t) { openModal('githubModal'); return; }
            btn.innerText = "...";
            const res = await fetch('/save', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({filename:FILE_CACHE[id].name, code:FILE_CACHE[id].code, gh_token:t, gh_repo:r}) });
            const data = await res.json();
            if(data.success) { btn.style.background="#238636"; btn.innerText="تم النشر ✅"; } else alert(data.message);
        }

        function checkGH() {
            const r = localStorage.getItem("ghRepo");
            if(r) {
                document.getElementById("ghDot").classList.add("connected");
                document.getElementById("ghForm").style.display="none";
                document.getElementById("ghConnected").style.display="block";
                document.getElementById("repoName").innerText = r;
            }
        }
        async function saveAndCloneGH() {
            const repo = document.getElementById("ghRepo").value, token = document.getElementById("ghToken").value;
            const res = await fetch('/clone', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({gh_repo:repo, gh_token:token}) });
            const data = await res.json();
            if(data.success) { localStorage.setItem("ghRepo", repo); localStorage.setItem("ghToken", token); checkGH(); closeModal('githubModal'); } else alert(data.message);
        }
        function disconnectGH() { localStorage.clear(); location.reload(); }
        window.onload = () => { checkGH(); updateUI(); };
        document.getElementById("userInput").addEventListener("keypress", (e) => { if(e.key === "Enter") send(); });
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return HTML_TEMPLATE.replace("__MODELS_META_PLACEHOLDER__", MODELS_META_JSON)

def agent_stream(model, messages, data, search):
    max_turns = 5
    current_turn = 0

    while current_turn < max_turns:
        response_generator = generate_response(model, messages, data, search)

        turn_buffer = ""
        is_tool_turn = False
        chunks_collected = []

        # المرحلة 1: معالجة التفكير (بث فوري للمتصفح)
        # المرحلة 2: فحص النص (حجب الجولات الوسيطة وبث الجولة النهائية)
        for chunk in response_generator:
            if "__THINK__" in chunk:
                yield chunk
            elif "__TEXT__" in chunk:
                # نبدأ في فحص النص للتأكد هل هو READ أم رد نهائي
                content = chunk.split("__TEXT__")[1] if "__TEXT__" in chunk else chunk
                turn_buffer += content
                chunks_collected.append(content)

                # ننتظر قليلاً للتأكد من وجود READ: في البداية
                if len(turn_buffer) > 20:
                    if "READ:" in turn_buffer[:50]:
                        is_tool_turn = True
                        # لا نرسل علامة النص للمتصفح في الجولات الوسيطة
                        break # نكسر الحلقة لاستكمال القراءة
                    else:
                        # جولة نهائية! نرسل علامة النص فوراً ونبدأ البث
                        yield "__TEXT__"
                        yield turn_buffer
                        # الآن نستمر في بث باقي الأجزاء فوراً
                        for remaining_chunk in response_generator:
                            yield remaining_chunk
                        return # انتهى العمل بالكامل

            elif turn_buffer: # في حال وصول أجزاء نصية مكملة
                turn_buffer += chunk
                chunks_collected.append(chunk)
                if not is_tool_turn and "READ:" in turn_buffer[:50]:
                    is_tool_turn = True
                    break

        # إذا كانت جولة أداة (READ)
        if is_tool_turn or "READ:" in turn_buffer:
            try:
                # استهلاك باقي المولد للحصول على النص الكامل
                for rest in response_generator: turn_buffer += rest

                filename = turn_buffer.split("READ:")[1].split()[0].strip()
                yield f"__ACTION__ START: {filename}__ACTION__ END"

                allowed_exts = ('.html', '.css', '.js', '.py', '.json', '.md', '.txt')
                if filename.endswith(allowed_exts) and os.path.exists(filename):
                    with open(filename, 'r', encoding='utf-8') as f:
                        file_content = f.read()

                    messages.append({"role": "assistant", "content": turn_buffer})
                    messages.append({"role": "user", "content": f"FILE_CONTENT ({filename}):\n```\n{file_content}\n```"})
                    current_turn += 1
                    continue
            except: pass

        break

@app.route('/stream', methods=['POST'])
def stream():
    data = request.json
    try:
        file_list = []
        allowed_exts = ('.html', '.css', '.js', '.py', '.json', '.md', '.txt')
        for filename in os.listdir('.'):
            if filename.endswith(allowed_exts) and not filename.startswith('.'):
                file_list.append(filename)
        file_tree_str = "\n".join(file_list)

        system_rules = f"""
You are an expert Full-Stack Developer.
Files in directory: {file_tree_str}

PROTOCOL:
1. Think deeply.
2. To read a file, output ONLY: READ: filename.ext (e.g. READ: index.html).
3. If no files are needed, provide the final answer/code directly.
4. Output code inside triple backticks.
"""
        messages = [
            {"role": "system", "content": system_rules},
            {"role": "user", "content": data.get("message")}
        ]
        return Response(stream_with_context(agent_stream(data.get("model"), messages, data, data.get("search"))), mimetype='text/event-stream')
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/save', methods=['POST'])
def save():
    d = request.json
    try:
        with open(d['filename'], "w", encoding="utf-8") as f: f.write(d['code'])
        repo = get_safe_repo_name(d['gh_repo'])
        remote_url = f"https://x-access-token:{d['gh_token']}@github.com/{repo}.git"
        subprocess.run(["git", "remote", "remove", "origin"], check=False)
        subprocess.run(["git", "remote", "add", "origin", remote_url], check=True)
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "AI Update"], check=True)
        res = subprocess.run(["git", "push", "origin", "main", "--force"], capture_output=True, text=True)
        if res.returncode != 0: res = subprocess.run(["git", "push", "origin", "master", "--force"], capture_output=True, text=True)
        return jsonify({"success": res.returncode == 0, "message": res.stderr if res.returncode != 0 else ""})
    except Exception as e: return jsonify({"success": False, "message": str(e)})

@app.route('/clone', methods=['POST'])
def clone():
    d = request.json
    repo_name = get_safe_repo_name(d['gh_repo'])
    remote_url = f"https://x-access-token:{d['gh_token'].strip()}@github.com/{repo_name}.git"
    try:
        if os.path.exists(".git"): shutil.rmtree(".git")
        subprocess.run(["git", "init"], check=True)
        subprocess.run(["git", "remote", "add", "origin", remote_url], check=True)
        res = subprocess.run(["git", "pull", "origin", "main"], capture_output=True)
        if res.returncode != 0: subprocess.run(["git", "pull", "origin", "master"], check=True)
        return jsonify({"success": True})
    except Exception as e: return jsonify({"success": False, "message": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
