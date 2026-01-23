# Time Detection

Does this message contain a time reference (like "3pm", "14:30", "at 10")?

NOT times: scores (3:2), odds (5:1), ratios (16:9), bible verses (John 3:16), page/room numbers.

Message: "{{ message }}"

Reply ONLY with JSON, no explanation:
{"contains_time": true} or {"contains_time": false}

Examples:

- "Meeting at 3pm" → {"contains_time": true}
- "I have 3 cats" → {"contains_time": false}
- "Call at 14:30" → {"contains_time": true}
- "Score 3:16" → {"contains_time": false}
- "16:9 monitor" → {"contains_time": false}
- "John 3:16" → {"contains_time": false}
- "Odds are 5:1" → {"contains_time": false}
- "Mix ratio 2:1" → {"contains_time": false}
