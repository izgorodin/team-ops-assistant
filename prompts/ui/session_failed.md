{% if verify_url %}
😕 I couldn't determine your timezone from that.

Please use the <a href="{{ verify_url }}">web verification link</a> to set your timezone automatically, or try again with a major city name.
{% else %}
😕 I couldn't determine your timezone from that.

Please try again with a major city name (e.g., London, Tokyo, New York) or a timezone code (e.g., PT, CET, JST).
{% endif %}
