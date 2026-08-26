# Real-time

The intended boundary is provider/node event → event gateway → queue → normalizer → monitoring engine → graph/pattern/risk → alert. The first slice has no live event path. Historical provider retrieval is labeled `HISTORICAL`; polling every second is deliberately not used as a substitute.
