# OpenBMB/ClawXRouter

Audit generated: 2026-05-27T23:58:06.528733+00:00
Local clone: `repos-audit\OpenBMB__ClawXRouter`

## GitHub Metrics (Scrapling probe)

- **stars_abbrev:** 174
- **stars_exact:** 174
- **forks:** 21
- **open_issues:** 3
- **open_prs:** 0
- **description:** Contribute to OpenBMB/ClawXRouter development by creating an account on GitHub.

## Git Snapshot

- branch: `main`
- head:   `6acac9f8ae1a8c2c236b84deb68b5df4d2d6336f`
- last commit: 2026-03-31 16:35:17 +0800 6acac9f Kaguya-19
- contributors in shallow clone: 1
- top contributors (shallow):
    1	Kaguya-19 <liyishanthu@gmail.com>

## License

_(no LICENSE file found)_

## Languages (by total bytes — top 10)

- `.mp4`: 5,213,879 bytes
- `.png`: 838,219 bytes
- `.ts`: 467,325 bytes
- `.json`: 72,347 bytes
- `.md`: 58,517 bytes
- `(noext)`: 6,334 bytes
- `.mjs`: 981 bytes

## Dependencies

_(no dependency manifest detected)_
## README — first 80 lines

```
<div align="center">
  <img src="assets/clawxrouter-logo.png" alt="ClawXRouter Logo" width="65%">
</div>

<h3 align="center">
Secure · Efficient · Balanced
</h3>

<p align="center">
  Edge-Cloud Collaborative AI Agent Routing Plugin<br>
  <b>ClawXRouter</b>: Automatically route every request through the best path
</p>

<p align="center">
  <a href="../LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" alt="MIT License"></a>
  <a href="https://github.com/openbmb/clawxrouter"><img src="https://img.shields.io/github/stars/openbmb/clawxrouter?style=for-the-badge" alt="Stars"></a>
  <a href="https://github.com/openbmb/clawxrouter/issues"><img src="https://img.shields.io/github/issues/openbmb/clawxrouter?style=for-the-badge" alt="Issues"></a>
</p>

<p align="center">
    【<a href="./README_zh.md"><b>中文</b></a> | English】
</p>

---

**What's New** 🔥

- **[2026.03.25]** 🎉 ClawXRouter is now open source — Edge-Cloud Collaborative AI Agent Routing

---

## 📑 Table of Contents

- [💡 About ClawXRouter](#-about-clawxrouter)
- [🎬 Demo](#-demo)
- [📦 Quick Start](#-quick-start)
- [📈 Cost-Effective Routing: Beat Sonnet at 40% of the Price!](#-cost-effective-routing-beat-sonnet-at-40-of-the-price)
- [🔧 Custom Configuration](#-custom-configuration)
- [🔌 Supported Edge Providers](#-supported-edge-providers)
- [🔒 Three-Level Privacy Routing](#-three-level-privacy-routing)
- [💰 Cost-Aware Routing](#-cost-aware-routing)
- [🚀 Composable Routing Pipeline](#-composable-routing-pipeline)
- [🏗️ Code Structure](#️-code-structure)
- [🤝 Contributing](#-contributing)
- [📖 References](#-references)

---

## 💡 About ClawXRouter

ClawXRouter is an **Edge-Cloud Collaborative AI Agent Routing Plugin**, jointly developed by [THUNLP (Tsinghua University)](https://nlp.csai.tsinghua.edu.cn), [Renmin University of China](http://ai.ruc.edu.cn/), [AI9Stars](https://github.com/AI9Stars), [ModelBest](https://modelbest.cn/en), and [OpenBMB](https://www.openbmb.cn/home), built on top of [OpenClaw](https://github.com/openclaw/openclaw), based on [EdgeClaw](https://github.com/openbmb/Edgeclaw).

AI Agents are profoundly changing how developers work every day. However, during real-world deployment, the current Agent usage patterns expose three major problems: **"afraid to use" the cloud** (privacy leakage), **"can't afford" the cloud** (even simple tasks burn expensive tokens), and **"can't rely on" the edge** (local models can't handle hard tasks).

To address these three pain points, ClawXRouter provides corresponding solutions:

- **🔒 Afraid to use → Three-Level Privacy Routing**: Automatically identifies sensitive data. Confidential information (S3) is physically isolated locally, processed offline by edge models, and completely invisible to the cloud — fundamentally eliminating leakage risk so users can **use it with confidence**. When code review encounters an API Key, the request never leaves the machine.
- **💰 Can't afford → Cost-Aware Routing**: An edge-side small model acts as LLM-as-Judge, classifying tasks into five complexity levels and routing them to cloud models at different price tiers — saving 58% in costs while scoring 6.3% higher on PinchBench, so users can **afford to use it**. Grepping a function name goes to a cheap model instead of an expensive top-tier one.
- **🔗 Can't rely on → Smart Redaction & Forwarding**: For complex tasks involving sensitive information where edge models fall short, there's no need to struggle — for scenarios like multi-file complex data analysis, data is automatically redacted before forwarding to the cloud (S2), protecting privacy while leveraging cloud expertise, so users can **use it effectively**.
- **🎛️ Personalization → Composable Pipeline & Dashboard**: Privacy routing and cost-aware routing work together in the same pipeline through weighting and short-circuit strategies, complemented by a visual Dashboard that supports rule customization, instant configuration changes, and real-time testing, allowing every user to flexibly adjust according to their own needs.

Both routing systems run in the same composable pipeline: the edge-side dual engine (rule detection ~0ms + local LLM semantic detection ~1-2s) evaluates the sensitivity and complexity of each request in real-time, with security-first short-circuiting and cost optimization applied as needed. Developers don't need to modify business logic to achieve seamless edge-cloud collaboration: **"public data to the cloud, sensitive data redacted, confidential data stays local"**.


<div align="center">
  <img src="assets/clawxrouter-arch.png" alt="ClawXRouter Architecture" width="90%">
</div>

---

## 🎬 Demo

<div align="center">
  <video src="https://github.com/user-attachments/assets/c07e4ed4-1065-4be4-bbf7-6e918623aeb2" width="70%" controls></video>
</div>

---

## 📦 Quick Start

```
