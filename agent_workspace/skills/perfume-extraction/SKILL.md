---
name: perfume-extraction
description: Find a perfume's top, heart (middle), and base notes using only the perfume-finder MCP server. Use for perfume note lookups and structured fragrance extractions, including misspelled perfume names.
---

# Perfume extraction

## Source restriction

Use only tools from the configured perfume-finder MCP server for perfume information. Read their descriptions to choose the appropriate search and detail tools. Never call internet_search, another search service, another MCP server, or browse external pages to supplement or verify perfume data. Do not supply perfume facts from model knowledge, memory, or previous output files. Source URLs returned by the server may be cited without opening them.

## Identify and retrieve

- Search for the requested perfume using perfume-finder.
- You may correct obvious spelling mistakes and expand recognizable brand abbreviations in the query. For example, "JPG La Male La Parfume" may be searched as "Jean Paul Gaultier Le Male Le Parfum". A correction is a search aid, not evidence that the product or its notes were found.
- If the original query has no match, try the obvious corrected name when applicable. Stop after those reasonable queries; do not fall back to web search.
- Verify the brand, fragrance name, and concentration against the server result. Do not substitute a similarly named fragrance or a different concentration. If multiple plausible matches remain, ask which one the user means.
- Use the server's detail tools when available and needed to obtain the matched perfume's note layers.

## Extract the three layers

- Extract all reported notes separately under top notes, heart (middle) notes, and base notes. These are three layers, not a limit of three individual notes.
- Preserve the server's layer classifications. Do not infer layers from an unordered list, accords, or ingredients.
- If the server identifies the perfume but omits a layer, label that layer "Not provided by the perfume-finder MCP server." Report the available layers without guessing.
- Follow the requested output format. Otherwise provide the confirmed perfume name, brand and concentration when available, the three note lists, and source links returned by the server.
- When the user requests a file and perfume data is available, save the extraction at the requested workspace path and read it back to verify it.

## No result or server failure

If successful server queries return no information about the requested perfume, respond only:
"The perfume-finder MCP server doesn't contain any information about [perfume name]."

Use the corrected name if the spelling correction is unambiguous. Do not add remembered notes, recommendations, alternative sources, or an offer to search the web. Do not create a perfume extraction file when no perfume information was found.

A connection failure or tool error is not evidence that the server has no information. If a server error prevents the lookup, respond only:
"The perfume-finder MCP server could not be queried, so I couldn't retrieve information about [perfume name]."
