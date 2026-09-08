MATCH (p:Paper) RETURN count(p) AS papers;
MATCH (a:Author) RETURN count(a) AS authors;
MATCH (i:Institution) RETURN count(i) AS institutions;
MATCH (t:Topic) RETURN count(t) AS topics;
MATCH ()-[r:CITES]->() RETURN count(r) AS citations;
MATCH ()-[r:AUTHORED]->() RETURN count(r) AS authored_edges;
MATCH ()-[r:AFFILIATED_WITH]->() RETURN count(r) AS affiliation_edges;
MATCH ()-[r:HAS_TOPIC]->() RETURN count(r) AS topic_edges;

MATCH (p:Paper)
WITH p, count { (p)-[:CITES]-() } AS degree
ORDER BY degree DESC
LIMIT 1
MATCH (p)-[:CITES*1..2]-(neighbor:Paper)
RETURN p.paper_id AS seed_paper_id,
       p.title AS seed_title,
       degree,
       count(DISTINCT neighbor) AS two_hop_neighbors;

CALL gds.graph.drop('citationGraph', false) YIELD graphName
RETURN graphName;
CALL gds.graph.project('citationGraph', 'Paper', {CITES: {orientation: 'NATURAL'}})
YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount;
CALL gds.pageRank.stream('citationGraph')
YIELD nodeId, score
RETURN gds.util.asNode(nodeId).paper_id AS paper_id,
       gds.util.asNode(nodeId).title AS title,
       score
ORDER BY score DESC
LIMIT 20;
