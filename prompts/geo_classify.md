# Geo Intent Classification

Classify the intent of a message that mentions a city.

Message: "{{ text }}"
Detected city: {{ city }}

What is the user's intent?

- **time_query**: User asking about time/scheduling in that city (e.g., "в 15 по москве", "what time is it in London")
- **relocation**: User moved to, is in, or traveling to that city (e.g., "я в москве", "I moved to Berlin", "now in Paris")
- **false_positive**: City mentioned but NOT about time or location change (e.g., "москва - столица", "I love Tokyo food")
- **uncertain**: Cannot determine intent from the message

Reply with ONLY one word: time_query, relocation, false_positive, or uncertain
