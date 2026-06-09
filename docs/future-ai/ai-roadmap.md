# AI Roadmap

Planned enhancements, improvements, and optimization opportunities for when AI is reactivated.

---

## Phase 1: Reactivation (Post-MVP Validation)

### 1.1 Core AI Reactivation
- [ ] Enable AI via feature flags
- [ ] Restore AI endpoints
- [ ] Start AI Celery workers
- [ ] Validate end-to-end AI pipeline
- [ ] Performance baseline measurements

### 1.2 Model Updates
- [ ] Upgrade Ollama to latest version
- [ ] Evaluate newer models (Llama 4, Mistral, etc.)
- [ ] Benchmark quality vs. current models
- [ ] Update model pins in config

### 1.3 Monitoring
- [ ] AI-specific Grafana dashboards
- [ ] Cost per job tracking
- [ ] Model quality scoring
- [ ] User feedback aggregation

---

## Phase 2: Quality Improvements

### 2.1 Prompt Engineering
- [ ] A/B test prompt variations
- [ ] Optimize for accuracy (fewer hallucinations)
- [ ] Trade-specific prompt templates (HVAC, plumbing, electrical)
- [ ] Multi-turn conversation support

### 2.2 Output Quality
- [ ] Confidence threshold tuning
- [ ] Fallback output improvements
- [ ] Human-in-the-loop review workflow
- [ ] Automatic retry with alternative prompts on low confidence

### 2.3 Validation
- [ ] Structured output schema enforcement
- [ ] Material/cost accuracy verification
- [ ] Cross-reference with historical data

---

## Phase 3: New AI Features

### 3.1 AI Ticket Generation
- [ ] Voice-to-ticket workflows
- [ ] Photo-to-diagnosis
- [ ] Automated problem classification

### 3.2 AI Summaries
- [ ] Job history summarization
- [ ] Customer communication summaries
- [ ] Invoice/estimate narrative generation

### 3.3 AI Recommendations
- [ ] Material recommendations based on job type
- [ ] Pricing suggestions based on market data
- [ ] Upsell/cross-sell recommendations

### 3.4 AI Chat
- [ ] Customer-facing AI chatbot
- [ ] Internal AI assistant for technicians
- [ ] Knowledge base integration

### 3.5 Document Processing
- [ ] Invoice OCR
- [ ] Receipt processing
- [ ] Equipment manual parsing

---

## Phase 4: Performance & Scalability

### 4.1 Performance
- [ ] Model quantization (smaller footprint)
- [ ] Batch processing for multiple jobs
- [ ] Response caching for similar jobs
- [ ] Streaming responses (faster time-to-first-token)

### 4.2 Scalability
- [ ] Multiple Ollama replicas with load balancing
- [ ] GPU pool management
- [ ] Queue priority (premium users first)
- [ ] Geographic distribution (edge inference)

### 4.3 Cost Optimization
- [ ] Tiered model selection (cheap for simple, premium for complex)
- [ ] Caching layer for repeat queries
- [ ] Token usage optimization
- [ ] Batch discount from cloud providers

---

## Phase 5: Advanced AI

### 5.1 RAG Pipelines
- [ ] Vector search over historical jobs
- [ ] Knowledge base retrieval for recommendations
- [ ] Embedding-based job similarity

### 5.2 Multi-Modal AI
- [ ] Combined audio + image + text analysis
- [ ] Video processing for job walkthroughs
- [ ] Document understanding (PDFs, manuals, diagrams)

### 5.3 Predictive AI
- [ ] Job duration prediction
- [ ] Cost estimation from historical data
- [ ] Equipment failure prediction
- [ ] Seasonal demand forecasting

---

## Technical Debt (Known Issues)

| Issue | Severity | Description |
|---|---|---|
| Model version pinning | Medium | Models are pinned but should be tested before upgrade |
| Prompt injection defense | Low | Current defense is comprehensive but should be audited regularly |
| Circuit breaker tuning | Low | Half-open probe timing may need adjustment under load |
| ACU cost estimation | Medium | Cost model may need recalibration with new models |
| WebSocket scalability | Medium | Current design supports ~500 connections per replica |
| DLQ recovery | Low | Manual intervention sometimes needed for edge cases |

---

## Security Roadmap

- [ ] Regular prompt injection penetration testing
- [ ] Model output safety classification
- [ ] Data leakage prevention for training data
- [ ] SOC 2 compliance for AI data handling
- [ ] AI-specific penetration testing

---

## Timeline (Tentative)

| Phase | Duration | Effort |
|---|---|---|
| Phase 1: Reactivation | 2-4 weeks | 1-2 engineers |
| Phase 2: Quality | 4-8 weeks | 2-3 engineers |
| Phase 3: New Features | 8-16 weeks | 3-4 engineers |
| Phase 4: Performance | 4-8 weeks | 2 engineers |
| Phase 5: Advanced AI | 12-24 weeks | 3-5 engineers |
