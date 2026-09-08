CALL gds.graph.drop('citationCommunityGraph', false) YIELD graphName
RETURN graphName;
CALL gds.graph.project(
  'citationCommunityGraph',
  'Paper',
  {CITES: {orientation: 'UNDIRECTED'}}
)
YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount;
CALL gds.louvain.write(
  'citationCommunityGraph',
  {writeProperty: 'citationCommunity'}
)
YIELD communityCount, modularity, nodePropertiesWritten
RETURN communityCount, modularity, nodePropertiesWritten;
CALL gds.graph.drop('citationCommunityGraph') YIELD graphName
RETURN graphName;

CALL gds.graph.drop('citationRankGraph', false) YIELD graphName
RETURN graphName;
CALL gds.graph.project(
  'citationRankGraph',
  'Paper',
  {CITES: {orientation: 'NATURAL'}}
)
YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount;
CALL gds.pageRank.write(
  'citationRankGraph',
  {writeProperty: 'citationPageRank'}
)
YIELD nodePropertiesWritten, ranIterations
RETURN nodePropertiesWritten, ranIterations;
CALL gds.graph.drop('citationRankGraph') YIELD graphName
RETURN graphName;
