# Conversation Matrix Graph

The 6-node architecture that makes AI conversations indistinguishable from human.

## The 6 Nodes

| Node | File | Status |
|------|------|--------|
| 1. Conversation DNA | `01_conversation_dna.md` | Building |
| 2. Persona Layer | `02_persona_layer.md` | Pending |
| 3. Hook System | `03_hook_system.md` | Pending |
| 4. Dual Memory | `04_memory.md` | Pending |
| 5. Conversation Scoring | `05_scoring.md` | Pending |
| 6. Delivery Engine | `06_delivery.md` | Pending |

## Architecture

Every operator inherits this graph. The operator customizes by:
- Dialing Laws up/down (Node 1)
- Plugging in their persona (Node 2)
- Setting their delivery channel (Node 6)
- Scoping their memory (Node 4)
- Setting score thresholds (Node 5)

## Origin

- 27 Laws extracted from: S2S 485, It Is What It Is, Ticket & The Truth
- Architecture harvested from: CHAMP V3, Claude Code, Graphiti, Mem0, Cognee
- Scoring concept from: Voice fingerprinting SECS methodology
- UI direction: Particle sphere on dark wave background (Figma)

## Universal Pattern

This 6-node graph is the first implementation. The same node + relationship + dial pattern applies to:
- Sales pipelines
- Client journeys
- Content funnels
- Nurturing sequences
- Any system with stages and relationships
