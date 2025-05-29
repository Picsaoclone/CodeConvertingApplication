from flask import Blueprint, request, jsonify
import openai
import cx_Oracle
from app.config import Config

main = Blueprint('main', __name__)
openai.api_key = Config.OPENAI_API_KEY

@main.route('/convert', methods=['POST'])
def convert_code():
    data = request.get_json()
    user_id = data.get('user_id')
    source_code = data.get('source_code')
    source_language = data.get('source_language')
    target_language = data.get('target_language')

    try:
        # Gọi OpenAI để chuyển đổi mã
        response = openai.ChatCompletion.create(
        model="gpt-4o-mini-2024-07-18", 
        messages=[
            {"role": "system", "content": "You are a helpful code converter."},
            {"role": "user", "content": f"Convert this code from {source_language} to {target_language}:\n{source_code}"}
        ],
        temperature=0.7
    )
        converted_code = response.choices[0].message['content'].strip()


        # Gọi stored procedure StoreCodeConversion trong Oracle
        dsn = cx_Oracle.makedsn("localhost", 1521, service_name="ORCL21")
        conn = cx_Oracle.connect(Config.ORACLE_USER, Config.ORACLE_PASSWORD, dsn)
        cursor = conn.cursor()

        cursor.callproc("StoreCodeConversion", [
            user_id,
            source_code,
            converted_code,
            source_language,
            target_language
        ])

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "converted_code": converted_code
        })

    except cx_Oracle.DatabaseError as e:
        # Lấy thông tin lỗi từ Oracle
        error_msg = str(e)

        # Kiểm tra lỗi ORA-20002 (vượt quá giới hạn chuyển đổi)
        if "ORA-20002" in error_msg:
            return jsonify({
                "status": "error",
                "message": "You have exceeded the daily conversion limit. Please try again later."
            })
        elif "ORA-20001" in error_msg:
            return jsonify({
                "status": "error",
                "message": "Invalid code"
            })
        
        # Nếu không phải lỗi ORA-20002, trả về thông báo lỗi chung
        return jsonify({
            "status": "error",
            "message": "An unexpected error occurred. Please try again later."
        })

@main.route('/register', methods=['POST'])
def register_user():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    try:
        # Kết nối đến Oracle
        dsn = cx_Oracle.makedsn("localhost", 1521, service_name="ORCL21")
        conn = cx_Oracle.connect(Config.ORACLE_USER, Config.ORACLE_PASSWORD, dsn)
        cursor = conn.cursor()

        # Lấy user_id từ sequence seq_user_id
        cursor.execute("SELECT seq_user_id.NEXTVAL FROM dual")
        user_id = cursor.fetchone()[0]

        # Kiểm tra xem username hoặc email đã tồn tại chưa
        cursor.execute("""
            SELECT COUNT(*) FROM Users WHERE username = :1 OR email = :2
        """, (username, email))

        count = cursor.fetchone()[0]

        if count > 0:
            # Nếu trùng thì trả về lỗi
            return jsonify({
                "status": "error",
                "message": "Username or email already exists."
            })

        # Nếu không trùng, insert user vào bảng Users
        cursor.execute("""
            INSERT INTO Users (user_id, username, email, password, created_at)
            VALUES (:1, :2, :3, :4, SYSDATE)
        """, (user_id, username, email, password))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": f"User '{username}' registered successfully!"
        })

    except cx_Oracle.IntegrityError as e:
        return jsonify({
            "status": "error",
            "message": "Username or email already exists."
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

    


import jwt
import datetime

@main.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    try:
        dsn = cx_Oracle.makedsn("localhost", 1521, service_name="ORCL21")
        conn = cx_Oracle.connect(Config.ORACLE_USER, Config.ORACLE_PASSWORD, dsn)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id, username FROM Users
            WHERE username = :1 AND password = :2
        """, (username, password))

        user = cursor.fetchone()

        if user:
            # Tạo JWT token sử dụng pyjwt.encode()
            token = jwt.encode({
                'user_id': user[0],
                'username': user[1],
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
            }, 'secret', algorithm='HS256')

            cursor.close()
            conn.close()

            return jsonify({
                "status": "success",
                "message": "Login successful",
                "token": token
            })

        cursor.close()
        conn.close()

        return jsonify({
            "status": "error",
            "message": "Invalid username or password"
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })


@main.route('/conversion_history/<int:user_id>', methods=['GET'])
def get_conversion_history(user_id):
    try:
        # Kết nối đến Oracle
        dsn = cx_Oracle.makedsn("localhost", 1521, service_name="ORCL21")
        conn = cx_Oracle.connect(Config.ORACLE_USER, Config.ORACLE_PASSWORD, dsn)
        cursor = conn.cursor()

        # Truy vấn lịch sử chuyển đổi của user
        cursor.execute("""
            SELECT cc.conversion_id, cc.source_language, cc.target_language, cc.conversion_time
            FROM Code_Conversions cc
            WHERE cc.user_id = :1
            ORDER BY cc.conversion_time DESC
        """, (user_id,))

        history = cursor.fetchall()

        cursor.close()
        conn.close()

        # Trả về kết quả dưới dạng JSON
        return jsonify({
            "status": "success",
            "history": history
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })


@main.route('/conversion_detail/<int:conversion_id>', methods=['GET'])
def get_conversion_detail(conversion_id):
    try:
        dsn = cx_Oracle.makedsn("localhost", 1521, service_name="ORCL21")
        conn = cx_Oracle.connect(Config.ORACLE_USER, Config.ORACLE_PASSWORD, dsn)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT source_code, converted_code
            FROM Code_Conversions
            WHERE conversion_id = :1
        """, (conversion_id,))

        result = cursor.fetchone()

        # Mở kết nối lại nếu có CLOB
        if result:
            source_code = result[0].read() if result[0] is not None else ""
            converted_code = result[1].read() if result[1] is not None else ""
            
            cursor.close()
            conn.close()

            return jsonify({
                "status": "success",
                "source_code": source_code,
                "converted_code": converted_code
            })
        else:
            cursor.close()
            conn.close()
            return jsonify({
                "status": "error",
                "message": "Conversion not found"
            })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })


@main.route('/get_conversion_count', methods=['GET'])
def get_conversion_count():
    user_id = request.args.get('user_id')

    try:
        # Kết nối Oracle
        dsn = cx_Oracle.makedsn("localhost", 1521, service_name="ORCL21")
        conn = cx_Oracle.connect(Config.ORACLE_USER, Config.ORACLE_PASSWORD, dsn)
        cursor = conn.cursor()

        # Gọi function PL/SQL GetRemainingConversions để lấy số lần chuyển đổi còn lại
        cursor.execute("""
            SELECT GetRemainingConversions(:user_id) FROM dual
        """, {'user_id': user_id})

        remaining_conversions = cursor.fetchone()[0]

        cursor.close()
        conn.close()
        print(f"Remaining conversions for user {user_id}: {remaining_conversions}")  # Kiểm tra giá trị trả về

        return jsonify({
            "status": "success",
            "remaining_conversions": remaining_conversions
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })
