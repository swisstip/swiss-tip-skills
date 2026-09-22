# Swiss TIP knowledge-base builder

A Claude Code plugin that builds a grounded, citable knowledge base out of
official web pages: it discovers the sources, crawls them, writes concepts and
facts that cite the saved pages, takes a person through review, and builds a
validated release. The releases it produces are served by the Swiss TIP MCP
server, so an assistant can answer from cited official pages instead of from
memory.

This repository holds the **plugin**: the skill, its references and scripts,
and the subagents that do the bulk of the work. The server and its pipeline are
in [swiss-tip](https://github.com/swisstip/swiss-tip), the knowledge bases it
serves in [swiss-tip-mvp](https://github.com/swisstip/swiss-tip-mvp).

## The hackathon

Built for the **Swiss {ai} Weeks** hackathon in Zurich, 24 and 25 September
2026, for the challenge **Swiss Grounding MCP**, set by Swisscom's myAI team:

<https://zh.ai-weeks.ch/challenges/swiss-grounding-mcp>

## Status

Initial setup. Contents are being added; this README will describe the plugin,
its installation and the steps it runs once they are in place.
