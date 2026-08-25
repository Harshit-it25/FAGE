# FAGE Pitch Deck: Slide-by-Slide Outline

This pitch is designed to be **brutal, fast, and unforgettable**. You are competing against 25+ teams. Most of them will start by saying *"Hi, we built a machine learning model that predicts fraud."* The judges will instantly fall asleep because they've heard it 24 times already.

You are going to wake them up by showing that you not only built exactly what they asked for in the problem statement—but you also solved the real-world operational problems that make standard models fail.

---

## Slide 1: The Hook (Title Slide)
**Visual:** A dark screen with a massive, bold number in red (e.g., ₹2,500 Crores).
**Your Script:** 
> *"Every single team here today is going to show you a classification model that predicts suspicious accounts with '95% accuracy.' And every single one of those models will fail in a real bank. Why? Because in the real world, fraud isn't a classification problem. It's a bandwidth problem. When you flood a SOC analyst with 10,000 false positives a day, they stop looking. The real fraud slips through, and the bank bleeds money.*
> *Your problem statement asked for a system capable of identifying mule accounts and generating intelligent alerts. We didn't just build a model. We built **FAGE (Financial AI Governance Engine)**. We built a system that hunts organized mule rings, optimizes for actual rupees saved instead of academic metrics, and automates the paperwork so analysts can actually do their jobs."*

---

## Slide 2: The FAGE Architecture & Workflow
**Visual:** The workflow diagram showing the end-to-end pipeline (you can build this graphic based on the diagram below).

```mermaid
graph TD
    %% Styling
    classDef data fill:#2d3436,stroke:#74b9ff,stroke-width:2px,color:white;
    classDef engine fill:#0984e3,stroke:#74b9ff,stroke-width:2px,color:white;
    classDef graph fill:#d63031,stroke:#ff7675,stroke-width:2px,color:white;
    classDef output fill:#00b894,stroke:#55efc4,stroke-width:2px,color:white;

    %% Workflow Nodes
    A[Raw Financial Transactions]:::data --> B[Feature Engineering\nVelocity, Structuring Bands]:::engine
    B --> C{Cost-Optimized XGBoost\nRisk Engine}:::engine
    C -- Low Risk / Cheap --> D[Auto-Clear\nNo Human Wasted]:::output
    C -- High Risk / Expensive --> E[Governance Service\nNetwork Graph Analysis]:::graph
    
    E --> F[Multi-Hop Mule Ring\nCorrelation Detection]:::graph
    F --> G[NVIDIA NIM LLM\n+ NeMo Guardrails]:::engine
    G --> H[Automated SAR Draft\nfor SOC Analyst]:::output
```

**Your Script:**
> *"Here is how data flows through FAGE. Raw transactions enter our pipeline where we instantly engineer behavioral features like 6-hour velocity and structuring bands. The data hits our XGBoost Risk Engine, which uses a Cost-Optimized threshold. If it's a low-risk, low-rupee transaction, we auto-clear it. If it's high risk, we escalate it to our Governance Graph, which scans the network for multi-hop mule rings. Finally, we pass the entire network to our LLM to instantly draft a Suspicious Activity Report (SAR)."*

---

## Slide 3: Answering the Prompt (Feature Engineering & Classification)
**Visual:** Quick flash of the data pipeline, showing raw transaction data transforming into engineered features (velocity, structuring).
**Your Script:**
> *"To solve the core problem you gave us, we didn't just dump raw data into a neural net. We extracted time-velocity metrics, detected near-threshold structuring bands (like ₹9k-₹10k transfers), and mapped temporal clusters. We fed this into our XGBoost classification engine to distinguish legitimate accounts from suspicious ones. But we quickly realized that a raw classification model isn't enough."*

---

## Slide 4: The Metrics & The Truth
**Visual:** Clean dashboard showing your key metrics: **ROC-AUC: 97% | PR-AUC: 86% | Precision: 79% (±0.11)**
**Your Script:**
> *"Our XGBoost classifier achieved a 97% ROC-AUC and an 86% PR-AUC, which is exceptionally strong for this imbalanced dataset. Our mean precision is 79%. Now, you will notice a ±11% variance in our precision across cross-validation folds. Why? Because we have fewer than 25 confirmed fraud cases in this dataset. We could have used SMOTE to artificially oversample the data and show you a fake 99% precision slide like everyone else. But we didn't, because SMOTE destroys precision in production. We kept the math honest, because our system isn't solely reliant on the classifier."*

---

## Slide 5: The Core Problem (The SOC Bottleneck)
**Visual:** A funnel showing thousands of transactions pouring in, squeezing into a tiny bottleneck labeled "Human SOC Analyst," with "False Positives" overflowing and burning money.
**Your Script:**
> *"The industry standard is broken. Current systems flag anything suspicious. The result? 90% false positive rates. Analysts spend 4 hours investigating a ₹10,000 transaction, which costs the bank more in labor than the actual fraud. Meanwhile, sophisticated mule networks slip right through because legacy systems only look at transactions in isolation. The prompt asked for 'predictive risk scoring' and 'intelligent alert generation.' Here is how FAGE delivers."*

---

## Slide 6: Pillar 1 – Predictive Risk Scoring via Cost-Optimization (Rupees, not ROC-AUC)
**Visual:** A chart comparing standard ML accuracy vs. FAGE's Cost Curve (showing rupees saved).
**Your Script:**
> *"Most data scientists optimize for F1 scores. We optimize for Rupees. FAGE dynamically shifts its predictive risk score based on the actual financial cost of a false positive versus a false negative. If a transaction is for ₹500, we don't waste human time. If it's for ₹5,00,000, we escalate. Our engine ensures that every alert sent to a human is mathematically worth their hourly rate."*

---

## Slide 7: Pillar 2 – Intelligent Alert Generation (The Mule Ring Graph)
**Visual:** A screenshot or live demo of the Network Graph component, highlighting 2-hop bridge accounts in red. 
**Your Script:**
> *"This is what separates FAGE from a toy model, and this is how we handle that 11% variance in precision. Fraudsters don't work alone. They use 'mules' to structure payments. When FAGE flags a transaction, it instantly scans up to 2 hops away in the database. It looks for bridge accounts and synchronized high-velocity patterns. We fulfill your requirement for 'intelligent alert generation' by handing the analyst the entire criminal network on a silver platter. If the ML model is uncertain, the graph correlation confirms the fraud."*

---

## Slide 8: Pillar 3 – Automated SARs (NVIDIA NIM + Guardrails)
**Visual:** A side-by-side of a complex JSON data dump vs. a clean, generated Suspicious Activity Report (SAR).
**Your Script:**
> *"When an analyst confirms fraud, they have to write a Suspicious Activity Report (SAR) for regulators. It's tedious, legal paperwork. We integrated NVIDIA NIM LLMs to instantly draft legally sound, plain-language SARs directly from the graph data. And because financial data is hyper-sensitive, we wrapped the LLM in NeMo Guardrails to guarantee zero hallucinations and strict data masking."*

---

## Slide 9: Security & Defense (Why it's Enterprise-Ready)
**Visual:** Icons representing Differential Privacy, JWT Auth, and Zero-Trust.
**Your Script:**
> *"Judges, we know you're looking for holes. FAGE was built defensively from day one. Our models are trained using Differential Privacy (Epsilon budgets) to ensure no PII can be reverse-engineered from the weights. Our APIs are locked down with rigorous JWT authentication. We even scrubbed and normalized our thresholds across the stack to ensure zero split-brain decisions in production. This isn't a hackathon project; this is a secure, enterprise-grade architecture."*

---

## Slide 10: The Conclusion / Q&A
**Visual:** The FAGE Logo, your team name, and the tagline: "Stop investigating alerts. Start dismantling networks."
**Your Script:**
> *"We answered your prompt. We performed the feature engineering, built the classification model, and engineered an intelligent alert system. But more importantly, we built FAGE to solve the actual problem banks face today: alert fatigue, isolated analytics, and massive labor costs. We are ready to show you how we save banks time, regulatory fines, and millions of rupees. Hit us with your hardest questions."*

---

### Tips for the Q&A (Be Brutal & Honest)
If they ask about **Why not Deep Learning/Neural Nets?**
*"Neural networks are black boxes. In finance, you have to explain to a regulator exactly WHY you blocked a transaction. We used XGBoost because it allows for deterministic feature importance (SHAP values), meaning we can legally defend every single decision FAGE makes."*
