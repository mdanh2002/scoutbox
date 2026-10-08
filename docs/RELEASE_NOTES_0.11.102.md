# ScoutBox 0.11.102

- Keeps all three Add Tracking Link controls on one aligned row at the normal modal width: Blog base URL with Open/Save, Article / short path with Test & Generate, and Import link with Scan DOCX Links. The short-path suffix input is intentionally compact.
- Marks the exact code-allocated suffix in the Test & Generate result using the same italic/accent treatment as the Tracking Links list.
- Corrects Statistics and Resource Usage date-filter toggles so an unchanged active preset/custom filter clears to All Data, while edited From/To values apply a custom range.
- Bases VRAM control visibility and VRAM chart rendering on a fresh current hardware sample, so Apple unified-memory systems hide it and systems exposing discrete VRAM show it independently of the selected historical range.
- Adds targeted regression checks for these 0.11.102 behaviors.

Next release: 0.11.103.
