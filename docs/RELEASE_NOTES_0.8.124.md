# ScoutBox 0.8.124

This release makes empty AI classification responses visible as warnings without turning them into false successes or normal provider errors.

- **AI Requests Warning status:** a provider request that returns no visible output is logged as `warning`. The Output column remains empty and the warning reason is available from the status/detail view.
- **Historical repair:** migration 0071 converts historical completed/synthetic-empty-output rows to Warning and annotates their metadata with `warning_code=empty_output`.
- **Provider telemetry semantics:** empty cloud output is not incremented as a normal provider error; genuine request/provider exceptions remain Failed/errors.
- **Dashboard warning:** three blank responses from the same provider/model/stage within 15 minutes create an operational AI-output warning. Five blank responses across mixed models/stages in the same window also trigger a general warning.
- **Notification toolbar:** the warning is included in the alert list and its badge refreshes through the normal attention endpoint. Red errors remain higher priority; warning-only alert state uses the amber warning badge.
- **Compatibility:** 0.8.123 history toolbar placement and automatic Local AI model preference are retained.
