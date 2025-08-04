from flask import Flask, request, jsonify, render_template_string, redirect
from zeep import Client, helpers
import yaml
import traceback
import sys

# ✅ 接收命令列參數當作 WSDL
if len(sys.argv) < 2:
    print("用法：python app.py <WSDL_URL>")
    sys.exit(1)

DEFAULT_WSDL = sys.argv[1]

app = Flask(__name__)
clients = {}
method_specs = {}
override_description = {}

# ✅ 移除輸入欄位的 UI
HTML_PAGE = f'''
<!DOCTYPE html>
<html>
<head>
  <title>SOAP ↔ OpenAPI 編輯器</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.13/codemirror.min.css">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.13/theme/dracula.min.css">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.13/addon/lint/lint.min.css">
  <style>
    html, body {{
      margin: 0;
      padding: 0;
      height: 100%;
    }}
    body {{
      display: flex;
      font-family: Arial, sans-serif;
    }}
    #left {{
      width: 50%;
      padding: 20px;
      box-sizing: border-box;
      border-right: 1px solid #ccc;
      display: flex;
      flex-direction: column;
      height: 100vh;
    }}
    #right {{
      width: 50%;
      height: 100vh;
    }}
    form {{
      flex: 1 1 auto;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      min-height: 0;
    }}
    #editor {{
      flex: 1 1 auto;
      min-height: 0;
      height: 100%;
      overflow: auto;
      border: 1px solid #ccc;
      font-size: 18px;
      margin-bottom: 8px;
    }}
  </style>
</head>
<body>
  <div id="left">
    <h3>OpenAPI YAML 編輯</h3>
    <form method="POST" action="/update_yaml" target="dummyframe" onsubmit="return syncEditor()">
      <textarea name="yaml" id="yamlArea" style="display:none;"></textarea>
      <div id="editor"></div>
      <button type="submit" style="margin-top: 12px;">更新 OpenAPI 文件</button>
    </form>
    <iframe name="dummyframe" style="display:none;"></iframe>
  </div>
  <div id="right">
    <iframe id="swagger" src="/docs?wsdl={DEFAULT_WSDL}" width="100%" height="100%" frameborder="0"></iframe>
  </div>

  <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.13/codemirror.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.13/mode/yaml/yaml.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.13/addon/lint/lint.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.13/addon/lint/yaml-lint.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/js-yaml/4.1.0/js-yaml.min.js"></script>
  <script>
    let editor = CodeMirror(document.getElementById('editor'), {{
      mode: 'yaml',
      theme: 'dracula',
      lineNumbers: true,
      gutters: ["CodeMirror-lint-markers"],
      lint: true,
      value: ''
    }});

    function resizeEditor() {{
      const editorContainer = document.getElementById('editor');
      const height = editorContainer.clientHeight;
      editor.setSize("100%", height);
    }}
    window.addEventListener('resize', resizeEditor);
    setTimeout(resizeEditor, 0);

    fetch('/swagger.yaml?wsdl={DEFAULT_WSDL}')
      .then(res => res.text())
      .then(text => {{
        editor.setValue(text);
        setTimeout(resizeEditor, 0);
      }});

    function syncEditor() {{
      try {{
        jsyaml.load(editor.getValue());
      }} catch (e) {{
        alert("YAML 格式錯誤：\\n" + e.message);
        return false;
      }}
      document.getElementById('yamlArea').value = editor.getValue();
      return true;
    }}
  </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/analyze')
def analyze():
    wsdl = request.args.get('wsdl') or DEFAULT_WSDL
    try:
        ensure_methods(wsdl)
        return jsonify({"methods": method_specs[wsdl]})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/update_yaml', methods=['POST'])
def update_yaml():
    try:
        yaml_text = request.form['yaml']
        doc = yaml.safe_load(yaml_text)
        override_description[DEFAULT_WSDL] = {}
        for path, method_obj in doc.get('paths', {}).items():
            for method, detail in method_obj.items():
                override_description[DEFAULT_WSDL][(path, method)] = detail.get('description')
        return "OK"
    except Exception as e:
        return f"Error: {e}", 400

@app.route('/swagger.yaml')
def swagger_yaml():
    wsdl = request.args.get("wsdl") or DEFAULT_WSDL
    ensure_methods(wsdl)
    spec = build_openapi_spec(wsdl)
    return yaml.dump(spec, allow_unicode=True)

@app.route('/swagger.json')
def swagger_json():
    wsdl = request.args.get("wsdl") or DEFAULT_WSDL
    ensure_methods(wsdl)
    spec = build_openapi_spec(wsdl)
    return jsonify(spec)

@app.route('/docs')
def docs():
    wsdl = request.args.get("wsdl") or DEFAULT_WSDL
    return redirect(f"/apidocs?url=/swagger.json?wsdl={wsdl}")

@app.route('/apidocs')
def apidocs():
    url = request.args.get('url', '/swagger.json')
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <title>Swagger UI</title>
      <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist/swagger-ui.css">
    </head>
    <body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist/swagger-ui-bundle.js"></script>
    <script>
      window.onload = function() {{
        window.ui = SwaggerUIBundle({{
          url: '{url}',
          dom_id: '#swagger-ui',
          presets: [
            SwaggerUIBundle.presets.apis,
            SwaggerUIBundle.SwaggerUIStandalonePreset
          ]
        }});
      }};
    </script>
    </body>
    </html>
    """

@app.route('/soap/<method>', methods=['POST'])
def soap_proxy(method):
    wsdl = request.args.get('wsdl') or DEFAULT_WSDL
    ensure_methods(wsdl)
    allowed_args = list(method_specs.get(wsdl, {}).get(method, {}).keys())
    if allowed_args is None:
        return jsonify({"error": f"No such method: {method}"}), 404
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400
    data = request.get_json(force=True, silent=True)
    if data is None or not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400
    call_args = {k: v for k, v in data.items() if k in allowed_args}
    try:
        client = clients.get(wsdl) or Client(wsdl)
        clients[wsdl] = client
        func = getattr(client.service, method)
        result = func(**call_args)
        return jsonify({"response": helpers.serialize_object(result)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def ensure_methods(wsdl):
    if wsdl not in method_specs:
        try:
            client = clients.get(wsdl) or Client(wsdl)
            clients[wsdl] = client
            methods = {}
            for service in client.wsdl.services.values():
                for port in service.ports.values():
                    for opname, op in port.binding._operations.items():
                        example = {}
                        if op.input.body and op.input.body.type:
                            for part in op.input.body.type.elements:
                                example[part[0]] = "<輸入值>"
                        methods[opname] = example
            method_specs[wsdl] = methods
        except Exception as e:
            traceback.print_exc()

def build_openapi_spec(wsdl):
    ensure_methods(wsdl)
    if wsdl not in method_specs:
        return {"openapi": "3.0.0", "info": {"title": "None", "version": "1.0"}, "paths": {}}
    methods = method_specs[wsdl]
    paths = {}
    for method_name, example in methods.items():
        path = f"/soap/{method_name}"
        desc = override_description.get(wsdl, {}).get((path, "post")) or f"Call SOAP: {method_name}"
        summary = method_name
        required = list(example.keys()) if example else []
        properties = {k: {"type": "string"} for k in example}
        request_schema = {
            "type": "object",
            "properties": properties,
            "example": example
        }
        if required:
            request_schema["required"] = required
        paths[path] = {
            "post": {
                "operationId": method_name,
                "summary": summary,
                "description": desc,
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": request_schema,
                            "example": example
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Success",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "response": {"type": "object"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    return {
        "openapi": "3.0.0",
        "info": {"title": "Dynamic SOAP Proxy", "version": "1.0"},
        "paths": paths
    }

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
