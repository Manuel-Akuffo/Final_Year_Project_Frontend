from flask import Flask, request, jsonify
from flask_cors import CORS
import joblib
import numpy as np
from groq import Groq
import sqlite3
import bcrypt
from datetime import datetime
import os
import re

# ── Environment Setup ──
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

app = Flask(__name__)
CORS(app)

# ── Load Model ──
model        = joblib.load("heart_model.pkl")
scaler       = joblib.load("scaler.pkl")
feature_cols = joblib.load("feature_cols.pkl")

# ── Groq Client ──
client = Groq(api_key=GROQ_API_KEY)


# ── Database ──
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mobile TEXT UNIQUE NOT NULL,
        pin TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        last_active TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS health_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        age INTEGER, gender INTEGER,
        height REAL, weight REAL, bmi REAL,
        systolic_bp INTEGER, diastolic_bp INTEGER, heart_rate INTEGER,
        diabetes INTEGER, smoking INTEGER,
        exercise_level INTEGER, family_history INTEGER,
        risk_label TEXT, risk_score REAL,
        checked_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    conn.commit()
    conn.close()

init_db()


def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn


def translate_to_twi(text):
    """Translate English text to Twi using Groq API"""
    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": f"Translate to Twi (Akan): {text}"}],
            max_tokens=500,
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Translation error: {e}")
        return text


def analyze_risk_factors(vitals):
    """Analyze which factors contribute to cardiovascular risk"""
    risk_factors = []

    systolic  = vitals.get('systolic_bp', 0)
    diastolic = vitals.get('diastolic_bp', 0)
    if systolic >= 140 or diastolic >= 90:
        risk_factors.append(f"High blood pressure ({systolic}/{diastolic} mmHg)")
    elif systolic >= 130 or diastolic >= 80:
        risk_factors.append(f"Elevated blood pressure ({systolic}/{diastolic} mmHg)")

    bmi = vitals.get('bmi', 0)
    if bmi >= 30:   risk_factors.append(f"Obesity (BMI {bmi})")
    elif bmi >= 25: risk_factors.append(f"Overweight (BMI {bmi})")

    age = vitals.get('age', 0)
    if age >= 65:   risk_factors.append(f"Age {age} (65+ years)")
    elif age >= 55: risk_factors.append(f"Age {age} (55+ years)")

    if vitals.get('smoking'):        risk_factors.append("Active smoking")
    if vitals.get('diabetes'):       risk_factors.append("Diabetes diagnosis")
    if vitals.get('family_history'): risk_factors.append("Family history of heart disease")

    if vitals.get('exercise_level', 1) == 0:
        risk_factors.append("Sedentary lifestyle (little to no exercise)")

    hr = vitals.get('heart_rate', 0)
    if hr >= 100: risk_factors.append(f"Elevated resting heart rate ({hr} bpm)")

    return risk_factors


def get_health_trend(user_id, limit=10):
    """Get user's health trend over time"""
    conn = get_db()
    records = conn.execute(
        'SELECT * FROM health_records WHERE user_id=? ORDER BY checked_at DESC LIMIT ?',
        (user_id, limit)
    ).fetchall()
    conn.close()

    trend_data = []
    for r in reversed(records):
        trend_data.append({
            'date':         r['checked_at'][:10],
            'systolic_bp':  r['systolic_bp'],
            'diastolic_bp': r['diastolic_bp'],
            'heart_rate':   r['heart_rate'],
            'bmi':          r['bmi'],
            'risk_score':   r['risk_score'],
            'risk_label':   r['risk_label']
        })
    return trend_data


# ── Auth Routes ──

@app.route('/register', methods=['POST'])
def register():
    try:
        data   = request.get_json()
        mobile = data.get('mobile', '').strip()
        pin    = data.get('password', '').strip()   # frontend sends field as 'password'

        # Validate mobile
        if not mobile:
            return jsonify({"error": "Mobile number is required"}), 400
        if not re.match(r'^\d{10}$', mobile):
            return jsonify({"error": "Mobile number must be exactly 10 digits"}), 400

        # Validate PIN
        if not pin:
            return jsonify({"error": "PIN is required"}), 400
        if not pin.isdigit():
            return jsonify({"error": "PIN must contain numbers only"}), 400
        if len(pin) != 4:
            return jsonify({"error": "PIN must be exactly 4 digits"}), 400

        # Hash PIN with bcrypt
        hashed_pin = bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (mobile, pin) VALUES (?, ?)",
                (mobile, hashed_pin)
            )
            conn.commit()
            return jsonify({"message": "Account created successfully!"})
        except sqlite3.IntegrityError:
            return jsonify({"error": "Mobile number already registered"}), 400
        finally:
            conn.close()

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/login', methods=['POST'])
def login():
    try:
        data   = request.get_json()
        mobile = data.get('mobile', '').strip()
        pin    = data.get('password', '').strip()   # frontend sends field as 'password'

        if not mobile or not pin:
            return jsonify({"error": "Mobile number and PIN are required"}), 400

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE mobile = ?", (mobile,)
        ).fetchone()
        conn.close()

        if not user:
            return jsonify({"error": "Mobile number not found"}), 401

        # Check against 'pin' column — fall back to 'password' for old accounts
        stored = user['pin'] if 'pin' in user.keys() else user['password']
        if not bcrypt.checkpw(pin.encode(), stored.encode()):
            return jsonify({"error": "Incorrect PIN"}), 401

        # Update last active
        conn = get_db()
        conn.execute(
            "UPDATE users SET last_active = ? WHERE id = ?",
            (datetime.now().isoformat(), user['id'])
        )
        conn.commit()
        conn.close()

        return jsonify({
            "message":  "Login successful",
            "user_id":  user['id'],
            "mobile":   user['mobile']
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/check-inactivity', methods=['POST'])
def check_inactivity():
    try:
        data    = request.get_json()
        user_id = data.get('user_id')
        conn    = get_db()
        user    = conn.execute(
            "SELECT last_active FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        conn.close()
        if not user:
            return jsonify({"inactive": False})
        days = (datetime.now() - datetime.fromisoformat(user['last_active'])).days
        return jsonify({"inactive": days >= 2, "days": days})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Prediction ──
@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.get_json()

        age            = float(data['age'])
        gender         = float(data['gender'])
        height         = float(data['height'])
        weight         = float(data['weight'])
        bmi            = round(weight / ((height / 100) ** 2), 2)
        systolic_bp    = float(data['systolic_bp'])
        diastolic_bp   = float(data['diastolic_bp'])
        heart_rate     = float(data['heart_rate'])
        diabetes       = float(data['diabetes'])
        smoking        = float(data['smoking'])
        exercise_level = float(data['exercise_level'])
        family_history = float(data['family_history'])
        user_id        = data.get('user_id')

        input_data = np.array([[
            age, gender, height, weight, bmi,
            systolic_bp, diastolic_bp, heart_rate,
            diabetes, smoking, exercise_level, family_history
        ]])

        input_scaled     = scaler.transform(input_data)
        risk_probability = model.predict_proba(input_scaled)[0]

        risk_score = round((risk_probability[1] * 50 + risk_probability[2] * 100), 1)
        risk_score = min(risk_score, 99.9)

        if risk_score < 30:   risk_label = "Low Risk"
        elif risk_score < 60: risk_label = "Moderate Risk"
        else:                 risk_label = "High Risk"

        if user_id:
            conn = get_db()
            conn.execute('''INSERT INTO health_records
                (user_id,age,gender,height,weight,bmi,systolic_bp,diastolic_bp,
                 heart_rate,diabetes,smoking,exercise_level,family_history,risk_label,risk_score)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (user_id, age, gender, height, weight, bmi, systolic_bp, diastolic_bp,
                 heart_rate, diabetes, smoking, exercise_level, family_history,
                 risk_label, risk_score))
            conn.execute("UPDATE users SET last_active=? WHERE id=?",
                         (datetime.now().isoformat(), user_id))
            conn.commit()
            conn.close()

        vitals_dict = {
            'age': age, 'gender': gender, 'systolic_bp': systolic_bp,
            'diastolic_bp': diastolic_bp, 'bmi': bmi, 'heart_rate': heart_rate,
            'smoking': smoking, 'diabetes': diabetes,
            'family_history': family_history, 'exercise_level': exercise_level
        }
        risk_factors = analyze_risk_factors(vitals_dict)

        return jsonify({
            "prediction":       risk_label,
            "risk_score":       risk_score,
            "bmi":              bmi,
            "risk_factors":     risk_factors,
            "risk_explanation": f"Your {risk_label.lower()} score is based on {len(risk_factors)} identified risk factor(s)."
        })

    except Exception as e:
        print(f"Prediction error: {e}")
        return jsonify({"error": str(e)}), 500


# ── Risk Explanation ──
@app.route('/risk-explanation/<int:user_id>', methods=['GET'])
def risk_explanation(user_id):
    try:
        conn        = get_db()
        last_record = conn.execute(
            'SELECT * FROM health_records WHERE user_id=? ORDER BY checked_at DESC LIMIT 1',
            (user_id,)
        ).fetchone()
        conn.close()
        if not last_record:
            return jsonify({"error": "No health records found"}), 404

        vitals = {
            'age': last_record['age'], 'gender': last_record['gender'],
            'systolic_bp': last_record['systolic_bp'], 'diastolic_bp': last_record['diastolic_bp'],
            'bmi': last_record['bmi'], 'heart_rate': last_record['heart_rate'],
            'smoking': last_record['smoking'], 'diabetes': last_record['diabetes'],
            'family_history': last_record['family_history'],
            'exercise_level': last_record['exercise_level']
        }
        risk_factors = analyze_risk_factors(vitals)

        return jsonify({
            "risk_score":   last_record['risk_score'],
            "risk_label":   last_record['risk_label'],
            "risk_factors": risk_factors,
            "checked_at":   last_record['checked_at'],
            "message":      f"Your {last_record['risk_label'].lower()} is based on {len(risk_factors)} risk factor(s)."
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Health Trend ──
@app.route('/trend/<int:user_id>', methods=['GET'])
def trend(user_id):
    try:
        trend_data = get_health_trend(user_id, limit=30)
        if not trend_data:
            return jsonify({"trend": [], "message": "No historical data yet"})

        avg_systolic   = np.mean([r['systolic_bp']  for r in trend_data])
        avg_diastolic  = np.mean([r['diastolic_bp'] for r in trend_data])
        avg_heart_rate = np.mean([r['heart_rate']   for r in trend_data])
        avg_bmi        = np.mean([r['bmi']          for r in trend_data])

        if len(trend_data) >= 2:
            latest   = trend_data[-1]['risk_score']
            previous = trend_data[-2]['risk_score']
            risk_trend = "improving" if latest < previous else "stable" if latest == previous else "worsening"
        else:
            risk_trend = "insufficient data"

        return jsonify({
            "trend": trend_data,
            "averages": {
                "systolic_bp":  round(avg_systolic, 1),
                "diastolic_bp": round(avg_diastolic, 1),
                "heart_rate":   round(avg_heart_rate, 1),
                "bmi":          round(avg_bmi, 2)
            },
            "risk_trend": risk_trend
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Records ──
@app.route('/records/<int:user_id>', methods=['GET'])
def get_records(user_id):
    try:
        conn    = get_db()
        records = conn.execute(
            'SELECT * FROM health_records WHERE user_id=? ORDER BY checked_at DESC',
            (user_id,)
        ).fetchall()
        conn.close()
        return jsonify({"records": [dict(r) for r in records]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Chat ──
@app.route('/chat', methods=['POST'])
def chat():
    try:
        data         = request.get_json()
        chat_history = data.get('history', [])
        prediction   = data.get('prediction', 'Unknown')
        risk_score   = data.get('risk_score', 0)
        vitals       = data.get('vitals', {})
        language     = data.get('language', 'english')
        user_id      = data.get('user_id')

        if not chat_history or chat_history[-1]['role'] != 'user':
            return jsonify({"error": "Invalid chat history"}), 400

        ex_map       = {0: 'Low', 1: 'Medium', 2: 'High'}
        risk_factors = analyze_risk_factors(vitals)
        trend_summary = ""
        if user_id:
            try:
                td = get_health_trend(user_id, limit=5)
                if len(td) >= 2:
                    diff = td[-1]['risk_score'] - td[-2]['risk_score']
                    trend_summary = f"\nRecent trend: {'IMPROVING' if diff < 0 else 'WORSENING'} (was {td[-2]['risk_score']}%, now {td[-1]['risk_score']}%)"
            except:
                pass

        risk_factors_str = ", ".join(risk_factors) if risk_factors else "No major risk factors identified"

        system_prompt = f"""You are HeartGuard AI, a friendly professional cardiovascular health assistant.

⚠️ DISCLAIMER: For educational purposes only. Always consult a doctor for medical decisions.

Patient Assessment:
- Risk Level: {prediction} ({risk_score}%)
- Risk Factors: {risk_factors_str}{trend_summary}
- Age: {vitals.get('age')}, Gender: {'Male' if vitals.get('gender')==1 else 'Female'}
- Height: {vitals.get('height')}cm, Weight: {vitals.get('weight')}kg, BMI: {vitals.get('bmi')}
- BP: {vitals.get('systolic_bp')}/{vitals.get('diastolic_bp')} mmHg, HR: {vitals.get('heart_rate')} bpm
- Diabetes: {'Yes' if vitals.get('diabetes') else 'No'}, Smoking: {'Yes' if vitals.get('smoking') else 'No'}
- Exercise: {ex_map.get(vitals.get('exercise_level',1),'Medium')}, Family History: {'Yes' if vitals.get('family_history') else 'No'}

Give personalised, practical advice. Be empathetic, concise (3-5 sentences). No markdown or asterisks."""

        messages = [{"role": "system", "content": system_prompt}] + chat_history

        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )

        english_reply = response.choices[0].message.content
        reply = translate_to_twi(english_reply) if language == 'akan' else english_reply

        return jsonify({"reply": reply, "original_english": english_reply})

    except Exception as e:
        print(f"Chat error: {e}")
        return jsonify({"error": str(e)}), 500


# ── What-If Risk Simulator ──
@app.route('/simulate', methods=['POST'])
def simulate():
    try:
        data = request.get_json()

        age            = float(data.get('age', 45))
        gender         = float(data.get('gender', 1))
        height         = float(data.get('height', 170))
        weight         = float(data.get('weight', 70))
        bmi            = round(weight / ((height / 100) ** 2), 2)
        systolic_bp    = float(data.get('systolic_bp', 120))
        diastolic_bp   = float(data.get('diastolic_bp', 80))
        heart_rate     = float(data.get('heart_rate', 72))
        diabetes       = float(data.get('diabetes', 0))
        smoking        = float(data.get('smoking', 0))
        exercise_level = float(data.get('exercise_level', 1))
        family_history = float(data.get('family_history', 0))
        scenarios      = data.get('scenarios', {})

        def get_risk(a,ge,h,w,bm,s,d,hr,dia,sm,ex,fh):
            inp = np.array([[a,ge,h,w,bm,s,d,hr,dia,sm,ex,fh]])
            sc  = scaler.transform(inp)
            p   = model.predict_proba(sc)[0]
            r   = round((p[1]*50 + p[2]*100), 1)
            return min(r, 99.9)

        baseline = get_risk(age,gender,height,weight,bmi,systolic_bp,diastolic_bp,
                            heart_rate,diabetes,smoking,exercise_level,family_history)

        results = [{"scenario":"Current Status","risk_score":baseline,"change":0,
                    "description":"Your current cardiovascular risk profile"}]

        if scenarios.get('quit_smoking'):
            r = get_risk(age,gender,height,weight,bmi,systolic_bp,diastolic_bp,
                         heart_rate,diabetes,0,exercise_level,family_history)
            results.append({"scenario":"Quit Smoking","risk_score":r,
                             "change":round(baseline-r,1),"description":f"Eliminate smoking → Risk: {r}%"})

        if scenarios.get('lose_weight_lbs'):
            nw  = max(weight - scenarios['lose_weight_lbs'], 30)
            nbm = round(nw/((height/100)**2), 2)
            r   = get_risk(age,gender,height,nw,nbm,systolic_bp,diastolic_bp,
                           heart_rate,diabetes,smoking,exercise_level,family_history)
            results.append({"scenario":f"Lose {scenarios['lose_weight_lbs']} lbs","risk_score":r,
                             "change":round(baseline-r,1),"description":f"BMI: {nbm} → Risk: {r}%"})

        if scenarios.get('lower_bp_systolic'):
            ns = max(systolic_bp - scenarios['lower_bp_systolic'], 90)
            nd = max(diastolic_bp - scenarios['lower_bp_systolic']*0.6, 60)
            r  = get_risk(age,gender,height,weight,bmi,ns,nd,
                          heart_rate,diabetes,smoking,exercise_level,family_history)
            results.append({"scenario":f"Lower BP by {scenarios['lower_bp_systolic']}","risk_score":r,
                             "change":round(baseline-r,1),"description":f"BP: {ns}/{int(nd)} → Risk: {r}%"})

        if scenarios.get('increase_exercise'):
            ne = min(float(scenarios['increase_exercise']), 2)
            r  = get_risk(age,gender,height,weight,bmi,systolic_bp,diastolic_bp,
                          heart_rate,diabetes,smoking,ne,family_history)
            results.append({"scenario":"Exercise 4+x/week","risk_score":r,
                             "change":round(baseline-r,1),"description":f"More exercise → Risk: {r}%"})

        return jsonify({"simulations": results})
    except Exception as e:
        print(f"Simulate error: {e}")
        return jsonify({"error": str(e)}), 500


# ── Action Plan Generator ──
@app.route('/action-plan', methods=['POST'])
def generate_action_plan():
    try:
        data         = request.get_json()
        risk_factors = data.get('risk_factors', [])
        risk_score   = data.get('risk_score', 0)
        vitals       = data.get('vitals', {})
        factors_str  = ", ".join(risk_factors) if risk_factors else "minimal identified risk factors"

        prompt = f"""Create a personalized 30-day cardiovascular health action plan for someone with:
Risk Level: {risk_score}%
Risk Factors: {factors_str}
Age: {vitals.get('age')}, BMI: {vitals.get('bmi')}
BP: {vitals.get('systolic_bp')}/{vitals.get('diastolic_bp')}

Format as a 4-week plan with specific, actionable steps. Keep it motivating and practical.
End with expected outcomes and a reminder to consult healthcare providers."""

        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.8
        )
        return jsonify({"plan": response.choices[0].message.content})
    except Exception as e:
        print(f"Action plan error: {e}")
        return jsonify({"error": str(e)}), 500


# ── Risk Trajectory ──
@app.route('/trajectory/<int:user_id>', methods=['GET'])
def predict_trajectory(user_id):
    try:
        trend_data = get_health_trend(user_id, limit=30)
        if len(trend_data) < 2:
            return jsonify({
                "trajectory": [],
                "prediction": "Insufficient data for prediction",
                "current_risk": 0 if not trend_data else trend_data[-1]['risk_score'],
                "predicted_risk_90d": "N/A"
            })

        risk_scores = [r['risk_score'] for r in trend_data]
        dates       = [r['date']       for r in trend_data]
        x     = np.arange(len(risk_scores))
        z     = np.polyfit(x, risk_scores, 1)
        slope = z[0]
        current_risk = risk_scores[-1]

        projection = []
        for days in [30, 60, 90]:
            val = current_risk + (slope * (len(risk_scores) * days / 30))
            val = max(0, min(val, 99.9))
            projection.append({
                "days_ahead":     days,
                "projected_risk": round(val, 1),
                "trend":          "improving" if slope < 0 else "stable" if abs(slope) < 0.1 else "worsening",
                "status":         "🟢 Low" if val < 30 else "🟡 Moderate" if val < 60 else "🔴 High"
            })

        if slope < -0.5:   trend_summary = "🟢 Strong improvement! Keep it up!"
        elif slope < 0:    trend_summary = "📈 Steady improvement. You're on track."
        elif slope < 0.5:  trend_summary = "➡️ Stable. Maintain current efforts."
        else:              trend_summary = "📉 Health declining. Consider consulting a doctor."

        return jsonify({
            "current_risk":       current_risk,
            "historical_dates":   dates[-10:],
            "historical_scores":  risk_scores[-10:],
            "trajectory":         projection,
            "trend_slope":        round(slope, 3),
            "trend_summary":      trend_summary,
            "predicted_risk_90d": round(projection[2]['projected_risk'], 1)
        })
    except Exception as e:
        print(f"Trajectory error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/')
def home():
    return "CardioSense AI is Running"


@app.route('/api', methods=['GET'])
def api_home():
    return "CardioSense AI API is Running"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)