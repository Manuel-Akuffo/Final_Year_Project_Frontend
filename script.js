// ── Auth Guard (Disabled - Direct Access) ──
const userId    = localStorage.getItem('hg_user_id') || '1';
const userMobile = localStorage.getItem('hg_mobile') || 'Demo User';
const userMobileEl = document.getElementById('userMobile');
if (userMobileEl) userMobileEl.textContent = '📱 ' + userMobile;

// ── Theme ──
function toggleTheme() {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  document.documentElement.setAttribute('data-theme', isDark ? 'light' : 'dark');
  localStorage.setItem('hg_theme', isDark ? 'light' : 'dark');
}
document.documentElement.setAttribute('data-theme', localStorage.getItem('hg_theme') || 'light');

// ── Global State ──
let currentPrediction = null;
let currentRiskScore  = 0;
let currentVitals     = {};
let currentRiskFactors = [];
let chatHistory       = [];
let isBotTyping       = false;
let chatLanguage      = 'english';

// ── Helpers ──
function logout()       { localStorage.removeItem('hg_user_id'); localStorage.removeItem('hg_mobile'); window.location.href = 'login.html'; }
function dismissAlert() { document.getElementById('alertBanner').style.display = 'none'; }
function getVal(id)     { return document.getElementById(id).value; }

function showError(msg) {
  const el = document.getElementById('errorMsg');
  el.textContent = '⚠ ' + msg;
  el.style.display = 'block';
}

function getBMICategory(bmi) {
  if (bmi < 18.5) return 'Underweight';
  if (bmi < 25)   return 'Normal';
  if (bmi < 30)   return 'Overweight';
  return 'Obese';
}

// ── Inactivity ──
async function checkInactivity() {
  try {
    const res  = await fetch('https://final-year-project-backend-q8cq.onrender.com/check-inactivity', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId })
    });
    const data = await res.json();
    if (data.inactive) {
      document.getElementById('alertBanner').style.display = 'flex';
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('💓 HeartGuard AI Reminder', {
          body: `You haven't checked your heart health in ${data.days} day(s). Check now!`
        });
      } else if ('Notification' in window && Notification.permission !== 'denied') {
        Notification.requestPermission().then(p => {
          if (p === 'granted') new Notification('💓 HeartGuard AI Reminder', {
            body: `You haven't checked in ${data.days} day(s). Check your heart health now!`
          });
        });
      }
    }
  } catch (e) { console.log('Inactivity check skipped'); }
}

// ── Risk Gauge ──
function drawGauge(score) {
  const colorClass = score < 30 ? 'low' : score < 60 ? 'moderate' : 'high';
  const label      = score < 30 ? 'Low Risk' : score < 60 ? 'Moderate Risk' : 'High Risk';
  const radius     = 80;
  const circ       = 2 * Math.PI * radius;
  const offset     = circ - (score / 100) * circ;

  document.getElementById('gaugeContainer').innerHTML = `
    <div class="gauge-svg-wrapper">
      <svg class="gauge-svg" viewBox="0 0 200 200">
        <circle class="gauge-bg" cx="100" cy="100" r="${radius}"/>
        <circle class="gauge-fill ${colorClass}" cx="100" cy="100" r="${radius}"
          stroke-dasharray="${circ}" stroke-dashoffset="${circ}" id="gaugeFill"/>
      </svg>
      <div class="gauge-center">
        <div class="gauge-percent ${colorClass}">${score}%</div>
        <div class="gauge-label ${colorClass}">${label}</div>
        <div class="gauge-sublabel">Risk Score</div>
      </div>
    </div>`;
  setTimeout(() => {
    const fill = document.getElementById('gaugeFill');
    if (fill) fill.style.strokeDashoffset = offset;
  }, 100);
}

// ── Risk Factors Display ──
function displayRiskFactors(factors) {
  const container = document.getElementById('gaugeContainer');
  
  if (!factors || factors.length === 0) {
    container.innerHTML += `
      <div style="margin-top: 24px; padding: 16px; background: var(--green-light); border-radius: 12px; border: 1px solid rgba(34,211,160,0.2); text-align: center;">
        <div style="font-weight: 600; color: var(--green); font-size: 14px;">✅ No Major Risk Factors</div>
        <div style="font-size: 12px; color: var(--text2); margin-top: 4px;">Keep maintaining your healthy lifestyle!</div>
      </div>`;
    return;
  }
  
  const factorsList = factors.map(f => `<li style="margin: 6px 0; font-size: 13px; color: var(--text2);">⚠️ ${f}</li>`).join('');
  
  container.innerHTML += `
    <div style="margin-top: 20px; padding: 16px; background: var(--accent-light); border-radius: 12px; border: 1px solid rgba(192,57,43,0.2);">
      <div style="font-weight: 700; color: var(--accent); font-size: 13px; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px;">📋 Identified Risk Factors (${factors.length})</div>
      <ul style="list-style: none; padding: 0; margin: 0;">
        ${factorsList}
      </ul>
      <div style="font-size: 11px; color: var(--text2); margin-top: 12px; line-height: 1.5;">💡 These factors contribute to your cardiovascular risk. Chat with HeartGuard AI below for personalized recommendations.</div>
    </div>`;
}

// ── Prediction ──
async function predict() {
  const fields = ['age','gender','height','weight','systolic_bp','diastolic_bp',
                  'heart_rate','diabetes','smoking','exercise_level','family_history'];

  for (const f of fields) {
    if (getVal(f) === '') { showError('Please fill in all fields before analyzing.'); return; }
  }

  document.getElementById('errorMsg').style.display = 'none';
  const btn = document.getElementById('predictBtn');
  btn.disabled = true;
  btn.textContent = 'Analyzing…';

  document.getElementById('gaugeContainer').innerHTML = `
    <div class="gauge-idle">
      <div style="width:48px;height:48px;border:4px solid var(--border-dark);border-top-color:var(--accent);border-radius:50%;animation:spin 0.8s linear infinite;margin:0 auto;"></div>
      <div class="gauge-idle-text" style="margin-top:16px">Analyzing your vitals…</div>
    </div>`;

  document.getElementById('scoreStrip').style.display = 'none';
  document.getElementById('chatSection').classList.remove('visible');

  const payload = {};
  for (const f of fields) payload[f] = Number(getVal(f));
  payload.user_id = userId;

  try {
    const response = await fetch('https://final-year-project-backend-q8cq.onrender.com/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) throw new Error(`Server error: ${response.status}`);
    const data = await response.json();

    currentPrediction = data.prediction;
    currentRiskScore  = data.risk_score;
    currentRiskFactors = data.risk_factors || [];
    currentVitals     = { ...payload, bmi: data.bmi };

    drawGauge(data.risk_score);

    document.getElementById('scoreVal').textContent = data.risk_score + '%';
    document.getElementById('bmiVal').textContent   = data.bmi;
    document.getElementById('bmiCat').textContent   = getBMICategory(data.bmi);
    document.getElementById('scoreStrip').style.display = 'grid';

    // Display risk factors
    displayRiskFactors(currentRiskFactors);

    // Show innovative features panels
    document.getElementById('simulatorCard').style.display = 'block';
    document.getElementById('actionPlanCard').style.display = 'block';
    document.getElementById('trajectoryCard').style.display = 'block';
    
    // Load content for innovative features
    setTimeout(() => loadActionPlan(), 1000);
    setTimeout(() => loadTrajectory(), 1000);

    setTimeout(() => openHistory(), 700);
    setTimeout(() => openChat(data.prediction, data.risk_score), 1300);

  } catch (err) {
    document.getElementById('gaugeContainer').innerHTML = `
      <div class="gauge-idle">
        <div class="gauge-idle-icon">🫀</div>
        <div class="gauge-idle-text">Awaiting analysis…</div>
      </div>`;
    showError('Could not connect to Flask API. Make sure your server is running on port 5000.');
    console.error(err);
  } finally {
    btn.disabled = false;
    btn.textContent = '⚡ Analyze My Cardiovascular Risk';
  }
}

// ── Chat ──
function openChat(prediction, riskScore) {
  const isHigh = prediction === 'High Risk';
  const isMod  = prediction === 'Moderate Risk';
  const chatSection = document.getElementById('chatSection');

  document.getElementById('chatMessages').innerHTML = '';
  chatHistory  = [];
  chatLanguage = 'english';
  document.getElementById('chatBtnEN').classList.add('active');
  document.getElementById('chatBtnTW').classList.remove('active');

  chatSection.classList.add('visible');
  chatSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

  const greeting = isHigh
    ? `Hello! I'm HeartGuard AI. 🛡️\n\nYour cardiovascular risk score is ${riskScore}% — HIGH RISK. Please don't panic, but this needs attention.\n\nI can explain your specific risk factors and recommend actionable steps. You should consider seeing a healthcare provider for a comprehensive evaluation.\n\nSwitch to 🇬🇭 Akan/Twi if you prefer!`
    : isMod
    ? `Hello! I'm HeartGuard AI. 🛡️\n\nYour cardiovascular risk score is ${riskScore}% — MODERATE RISK.\n\nThis is a good time to make lifestyle adjustments. I can help explain your risk factors and provide personalized recommendations.\n\nSwitch to 🇬🇭 Akan/Twi if you prefer.`
    : `Hello! I'm HeartGuard AI. 🛡️\n\nYour cardiovascular risk score is ${riskScore}% — LOW RISK. ✅\n\nGreat news! Let's keep it that way. I can help you maintain excellent heart health with personalized guidance.\n\nSwitch to 🇬🇭 Akan/Twi if you prefer!`;

  chatHistory.push({ role: 'assistant', content: greeting });
  setTimeout(() => { addBotMessage(greeting); showSuggestions(isHigh, isMod); }, 400);
}

function closeChat() { document.getElementById('chatSection').classList.remove('visible'); }

function showSuggestions(isHigh, isMod) {
  const s = isHigh
    ? ['🏥 Should I see a doctor now?', '🍎 What foods should I avoid?', '🏃 What exercises are safe?', '💊 What changes should I make?']
    : isMod
    ? ['📉 How do I lower my risk?', '🥗 What should I eat?', '🏃 How much exercise do I need?', '📊 What does my score mean?']
    : ['🥗 How do I stay heart healthy?', '🏃 Best exercises for my heart?', '😴 How does sleep affect my heart?', '📊 What does my score mean?'];
  document.getElementById('chatSuggestions').innerHTML = s.map(t =>
    `<button class="suggestion-btn" onclick="useSuggestion('${t}')">${t}</button>`).join('');
}

function useSuggestion(t) { document.getElementById('chatInput').value = t; sendChat(); }

function setChatLanguage(lang) {
  chatLanguage = lang;
  document.getElementById('chatBtnEN').classList.toggle('active', lang === 'english');
  document.getElementById('chatBtnTW').classList.toggle('active', lang === 'akan');
  addBotMessage(lang === 'akan'
    ? '🇬🇭 HeartGuard AI bɛka Twi kyerɛ wo. (Switched to Akan/Twi)'
    : '🇬🇧 HeartGuard AI will now respond in English.');
}

async function sendChat() {
  const input = document.getElementById('chatInput');
  const msg   = input.value.trim();
  if (!msg || isBotTyping) return;
  input.value = '';
  document.getElementById('chatSuggestions').innerHTML = '';
  addUserMessage(msg);
  chatHistory.push({ role: 'user', content: msg });
  isBotTyping = true;
  document.getElementById('chatSendBtn').disabled = true;
  showTyping();

  try {
    const res  = await fetch('https://final-year-project-backend-q8cq.onrender.com/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ history: chatHistory, prediction: currentPrediction,
        risk_score: currentRiskScore, vitals: currentVitals, language: chatLanguage, user_id: userId })
    });
    if (!res.ok) throw new Error(`${res.status}`);
    const data  = await res.json();
    const reply = data.reply || "I'm sorry, I had trouble responding. Please try again.";
    chatHistory.push({ role: 'assistant', content: reply });
    removeTyping();
    addBotMessage(reply);
  } catch (err) {
    removeTyping();
    chatHistory.pop();
    addBotMessage("I'm sorry, I had trouble responding. Please try asking again.");
  } finally {
    isBotTyping = false;
    document.getElementById('chatSendBtn').disabled = false;
  }
}

function addBotMessage(text) {
  const m = document.getElementById('chatMessages');
  const t = new Date().toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' });
  const d = document.createElement('div');
  d.className = 'chat-msg bot';
  d.innerHTML = `<div class="msg-avatar">🛡️</div><div><div class="msg-bubble">${text.replace(/\n/g,'<br/>')}</div><div class="msg-time">${t}</div></div>`;
  m.appendChild(d); m.scrollTop = m.scrollHeight;
}

function addUserMessage(text) {
  const m = document.getElementById('chatMessages');
  const t = new Date().toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' });
  const d = document.createElement('div');
  d.className = 'chat-msg user';
  d.innerHTML = `<div class="msg-avatar">🧑</div><div><div class="msg-bubble">${text}</div><div class="msg-time">${t}</div></div>`;
  m.appendChild(d); m.scrollTop = m.scrollHeight;
}

function showTyping() {
  const m = document.getElementById('chatMessages');
  const d = document.createElement('div');
  d.className = 'chat-msg bot'; d.id = 'typingIndicator';
  d.innerHTML = `<div class="msg-avatar">🛡️</div><div class="typing-dots"><span></span><span></span><span></span></div>`;
  m.appendChild(d); m.scrollTop = m.scrollHeight;
}

function removeTyping() { const e = document.getElementById('typingIndicator'); if (e) e.remove(); }

// ── History ──
function openHistory() {
  document.getElementById('historyPanel').classList.add('open');
  document.getElementById('historyOverlay').classList.add('visible');
  document.body.style.overflow = 'hidden';
  loadRecords();
}

function closeHistory() {
  document.getElementById('historyPanel').classList.remove('open');
  document.getElementById('historyOverlay').classList.remove('visible');
  document.body.style.overflow = '';
}

async function loadRecords() {
  const container = document.getElementById('historyRecords');
  container.innerHTML = '<div class="history-empty"><div class="history-empty-icon">⏳</div><p>Loading…</p></div>';
  try {
    const res     = await fetch(`https://final-year-project-backend-q8cq.onrender.com/records/${userId}`);
    const data    = await res.json();
    const records = data.records;

    if (!records || records.length === 0) {
      container.innerHTML = '<div class="history-empty"><div class="history-empty-icon">🫀</div><p>No records yet.<br/>Run your first prediction!</p></div>';
      ['totalChecks','totalLow','totalHigh'].forEach(id => document.getElementById(id).textContent = '0');
      return;
    }

    document.getElementById('totalChecks').textContent = records.length;
    document.getElementById('totalLow').textContent    = records.filter(r => r.risk_label === 'Low Risk').length;
    document.getElementById('totalHigh').textContent   = records.filter(r => r.risk_label === 'High Risk').length;

    container.innerHTML = records.map((r, i) => {
      const date = new Date(r.checked_at).toLocaleString();
      const cls  = r.risk_label === 'High Risk' ? 'risk' : r.risk_label === 'Moderate Risk' ? 'moderate' : 'healthy';
      return `
        <div class="history-record-card" style="animation-delay:${i*0.05}s">
          <div class="history-record-top">
            <span class="history-record-date">🕐 ${date}</span>
            <span class="record-badge ${cls}">${r.risk_label} — ${r.risk_score}%</span>
          </div>
          <div class="history-record-vitals">
            <div class="h-vital"><div class="v-val">${r.age}</div><div class="v-key">Age</div></div>
            <div class="h-vital"><div class="v-val">${r.systolic_bp}/${r.diastolic_bp}</div><div class="v-key">BP</div></div>
            <div class="h-vital"><div class="v-val">${r.heart_rate}</div><div class="v-key">HR bpm</div></div>
            <div class="h-vital"><div class="v-val">${r.bmi}</div><div class="v-key">BMI</div></div>
          </div>
        </div>`;
    }).join('');
  } catch (e) {
    container.innerHTML = '<div class="history-empty"><div class="history-empty-icon">⚠️</div><p>Could not load records.<br/>Make sure Flask is running.</p></div>';
  }
}

document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && document.activeElement !== document.getElementById('chatInput')) predict();
});

// ── INNOVATIVE FEATURES ──

// ── What-If Risk Simulator ──
async function runSimulation() {
  const scenarios = {
    quit_smoking: document.getElementById('simQuitSmoking').checked,
    lose_weight_lbs: parseFloat(document.getElementById('simWeightLoss').value) || 0,
    lower_bp_systolic: parseFloat(document.getElementById('simBPReduction').value) || 0,
    increase_exercise: document.getElementById('simExercise').checked ? 2 : 0
  };
  
  // Update slider displays
  document.getElementById('weightLossDisplay').textContent = scenarios.lose_weight_lbs + ' lbs';
  document.getElementById('bpReductionDisplay').textContent = scenarios.lower_bp_systolic + ' mmHg';
  
  try {
    const res = await fetch('https://final-year-project-backend-q8cq.onrender.com/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        age: currentVitals.age,
        gender: currentVitals.gender,
        height: currentVitals.height,
        weight: currentVitals.weight,
        bmi: currentVitals.bmi,
        systolic_bp: currentVitals.systolic_bp,
        diastolic_bp: currentVitals.diastolic_bp,
        heart_rate: currentVitals.heart_rate,
        diabetes: currentVitals.diabetes,
        smoking: currentVitals.smoking,
        exercise_level: currentVitals.exercise_level,
        family_history: currentVitals.family_history,
        scenarios: scenarios
      })
    });
    const data = await res.json();
    displaySimulationResults(data.simulations);
  } catch (e) {
    console.log('Simulation error:', e);
  }
}

function displaySimulationResults(simulations) {
  const container = document.getElementById('simulationResults');
  container.innerHTML = '';
  
  simulations.forEach((sim, idx) => {
    const isBaseline = idx === 0;
    const bgColor = isBaseline ? 'var(--bg2)' : sim.change > 0 ? 'rgba(34,211,160,0.1)' : 'var(--bg2)';
    const borderColor = isBaseline ? 'transparent' : sim.change > 0 ? 'rgba(34,211,160,0.5)' : 'transparent';
    
    const card = document.createElement('div');
    card.style.cssText = `
      padding: 12px; border-radius: 8px; background: ${bgColor};
      border: 1px solid ${borderColor}; display: flex; justify-content: space-between; align-items: center;
    `;
    card.innerHTML = `
      <div>
        <div style="font-weight: 600; color: var(--text1); margin-bottom: 2px;">${sim.scenario}</div>
        <div style="font-size: 12px; color: var(--text2);">${sim.description}</div>
      </div>
      <div style="text-align: right;">
        <div style="font-size: 18px; font-weight: 700; color: ${sim.risk_score < 30 ? '#22d3a0' : sim.risk_score < 60 ? '#f59e0b' : '#ef4444'}">${sim.risk_score}%</div>
        ${sim.change !== 0 ? `<div style="font-size: 12px; color: ${sim.change > 0 ? '#22d3a0' : '#ef4444'}; font-weight: 600;">↓ ${sim.change}</div>` : ''}
      </div>
    `;
    container.appendChild(card);
  });
}

// ── AI Action Plan ──
async function loadActionPlan() {
  const container = document.getElementById('actionPlanContent');
  container.innerHTML = '<div style="text-align: center; color: var(--text2);">⏳ Generating personalized 30-day plan...</div>';
  
  try {
    const res = await fetch('https://final-year-project-backend-q8cq.onrender.com/action-plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        risk_factors: currentRiskFactors,
        risk_score: currentRiskScore,
        vitals: currentVitals
      })
    });
    const data = await res.json();
    container.innerHTML = data.plan;
  } catch (e) {
    container.innerHTML = '❌ Failed to load action plan. Try again.';
    console.log('Action plan error:', e);
  }
}

function downloadActionPlan() {
  const text = document.getElementById('actionPlanContent').textContent;
  const element = document.createElement('a');
  element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(text));
  element.setAttribute('download', `ActionPlan_${new Date().toISOString().split('T')[0]}.txt`);
  element.style.display = 'none';
  document.body.appendChild(element);
  element.click();
  document.body.removeChild(element);
}

// ── Risk Trajectory Predictor ──
async function loadTrajectory() {
  try {
    const res = await fetch(`https://final-year-project-backend-q8cq.onrender.com/trajectory/${userId}`);
    const data = await res.json();
    
    // Update trend summary
    document.getElementById('trendSummary').textContent = data.trend_summary;
    document.getElementById('trendDetail').innerHTML = `
      Current Risk: <strong>${data.current_risk}%</strong> | 
      Projected 90 days: <strong>${data.predicted_risk_90d}%</strong> | 
      Trend: ${data.trend_slope > 0 ? '📈 Worsening' : data.trend_slope < 0 ? '📉 Improving' : '➡️ Stable'}
    `;
    
    // Draw chart
    drawTrajectoryChart(data.historical_dates, data.historical_scores);
    
    // Display projections
    const projContainer = document.getElementById('trajectoryProjections');
    projContainer.innerHTML = '';
    data.trajectory.forEach(proj => {
      const card = document.createElement('div');
      card.style.cssText = `
        padding: 12px; border-radius: 8px; background: var(--bg2); text-align: center;
        border: 1px solid rgba(255,255,255,0.1);
      `;
      const riskColor = proj.projected_risk < 30 ? '#22d3a0' : proj.projected_risk < 60 ? '#f59e0b' : '#ef4444';
      card.innerHTML = `
        <div style="font-size: 12px; color: var(--text2); margin-bottom: 5px;">+${proj.days_ahead} Days</div>
        <div style="font-size: 20px; font-weight: 700; color: ${riskColor};">${proj.projected_risk}%</div>
        <div style="font-size: 11px; color: var(--text2); margin-top: 5px;">${proj.status}</div>
      `;
      projContainer.appendChild(card);
    });
  } catch (e) {
    console.log('Trajectory error:', e);
  }
}

function drawTrajectoryChart(dates, scores) {
  const svg = document.getElementById('trajectoryChart');
  const padding = 40;
  const width = svg.clientWidth - 2 * padding;
  const height = svg.clientHeight - 2 * padding;
  
  svg.innerHTML = '';
  
  if (!dates || dates.length === 0) return;
  
  // Grid
  const gridGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  for (let i = 0; i <= 4; i++) {
    const y = padding + (i * height / 4);
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('x1', padding);
    line.setAttribute('y1', y);
    line.setAttribute('x2', padding + width);
    line.setAttribute('y2', y);
    line.setAttribute('stroke', 'rgba(255,255,255,0.1)');
    line.setAttribute('stroke-dasharray', '2,2');
    gridGroup.appendChild(line);
  }
  svg.appendChild(gridGroup);
  
  // Plot points and line
  const points = scores.map((score, i) => ({
    x: padding + (i / (scores.length - 1 || 1)) * width,
    y: padding + height - (score / 100) * height
  }));
  
  // Line path
  const pathData = points.map((p, i) => (i === 0 ? 'M' : 'L') + p.x + ',' + p.y).join(' ');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', pathData);
  path.setAttribute('fill', 'none');
  path.setAttribute('stroke', 'var(--accent)');
  path.setAttribute('stroke-width', '2');
  svg.appendChild(path);
  
  // Points
  points.forEach((p, i) => {
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', p.x);
    circle.setAttribute('cy', p.y);
    circle.setAttribute('r', '3');
    circle.setAttribute('fill', 'var(--accent)');
    svg.appendChild(circle);
  });
}

window.onload = () => { checkInactivity(); loadRecords(); };