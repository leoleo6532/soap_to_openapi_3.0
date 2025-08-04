from flask import Flask, request, jsonify
from flask_swagger_ui import get_swaggerui_blueprint

app = Flask(__name__)

@app.route('/add', methods=['POST'])
def add():
    data = request.get_json(force=True)
    a = data.get('a')
    b = data.get('b')
    return jsonify({"result": a + b})

@app.route('/openapi.json')
def openapi():
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "Addition API",
            "version": "1.0.0",
            "description": "提供兩個數字相加的服務。",
            "contact": {"name": "Leo6532", "email": "support@example.com"},
        },
        "paths": {
            "/add": {
                "post": {
                    "operationId": "add",                # MIT 點
                    "summary": "兩數相加",
                    "description": "輸入 a, b，回傳它們的總和。",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "a": {"type": "number", "description": "第一個數字"},
                                        "b": {"type": "number", "description": "第二個數字"}
                                    },
                                    "required": ["a", "b"]
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Operation result",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "result": {
                                                "type": "number",
                                                "description": "加總結果"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

SWAGGER_URL = '/docs'
API_URL = '/openapi.json'
swagger_ui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL, API_URL, config={"app_name": "Add Tool"}
)
app.register_blueprint(swagger_ui_blueprint, url_prefix=SWAGGER_URL)

if __name__ == "__main__":
    app.run(host="0.0.0.0",port=5001)
