# City Normalization Prompt

Convert this location to a CITY name that exists in geographic databases.

Input: "{{ city_name }}"

Rules:
- Abbreviations: NY → New York, MSK → Moscow
- Non-English: Москва → Moscow, Мадейра → Funchal
- Islands: Madeira → Funchal, Bali → Denpasar, Hawaii → Honolulu
- States/regions: Kentucky → Louisville, California → Los Angeles
- Already a city: Paris → Paris

Output ONLY the city name. If truly unknown, output: UNKNOWN
