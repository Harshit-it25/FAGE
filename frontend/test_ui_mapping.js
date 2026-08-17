import fetch from 'node-fetch';

async function test() {
  const response = await fetch('http://127.0.0.1:8000/api/alerts');
  if (!response.ok) {
    console.log("Error:", response.status);
    return;
  }
  const data = await response.json();
  const a = data.alerts[0];
  console.log("Raw API Alert:");
  console.log("risk_score:", a.risk_score);
  console.log("pu_probability:", a.pu_probability);
  console.log("confidence_interval_90:", JSON.stringify(a.explainability?.confidence_interval_90));

  const risk_score = a.risk_score || 0;
  const explainability = a.explainability || null;
  const ci = explainability?.confidence_interval_90 || null;
  
  let confidencePercent;
  if (ci && ci.width !== null) {
    confidencePercent = Math.round(Math.max(0, Math.min(100, 100 - ci.width * 100)));
  } else {
    confidencePercent = 0;
  }
  
  console.log("Mapped confidencePercent:", confidencePercent);
}

test();
