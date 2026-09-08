CREATE CONSTRAINT paper_id IF NOT EXISTS FOR (p:Paper) REQUIRE p.paper_id IS UNIQUE;
CREATE CONSTRAINT author_id IF NOT EXISTS FOR (a:Author) REQUIRE a.author_id IS UNIQUE;
CREATE CONSTRAINT institution_id IF NOT EXISTS FOR (i:Institution) REQUIRE i.institution_id IS UNIQUE;
CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.topic_id IS UNIQUE;

LOAD CSV WITH HEADERS FROM 'file:///papers.csv' AS row
CALL {
  WITH row
  MERGE (p:Paper {paper_id: row.`paper_id:ID(Paper)`})
  SET p.title = row.title,
      p.publication_year = CASE WHEN row.`publication_year:int` = '' THEN null ELSE toInteger(row.`publication_year:int`) END,
      p.doi = CASE WHEN row.doi = '' THEN null ELSE row.doi END,
      p.openalex_id = CASE WHEN row.openalex_id = '' THEN null ELSE row.openalex_id END,
      p.s2_id = CASE WHEN row.s2_id = '' THEN null ELSE row.s2_id END,
      p.s2_corpus_id = CASE WHEN row.s2_corpus_id = '' THEN null ELSE row.s2_corpus_id END,
      p.is_oa = toBoolean(row.`is_oa:boolean`)
} IN TRANSACTIONS OF 5000 ROWS;

LOAD CSV WITH HEADERS FROM 'file:///authors.csv' AS row
CALL {
  WITH row
  MERGE (a:Author {author_id: row.`author_id:ID(Author)`})
  SET a.display_name = row.display_name,
      a.openalex_id = CASE WHEN row.openalex_id = '' THEN null ELSE row.openalex_id END,
      a.orcid = CASE WHEN row.orcid = '' THEN null ELSE row.orcid END
} IN TRANSACTIONS OF 5000 ROWS;

LOAD CSV WITH HEADERS FROM 'file:///institutions.csv' AS row
CALL {
  WITH row
  MERGE (i:Institution {institution_id: row.`institution_id:ID(Institution)`})
  SET i.name = row.name,
      i.openalex_id = CASE WHEN row.openalex_id = '' THEN null ELSE row.openalex_id END,
      i.ror = CASE WHEN row.ror = '' THEN null ELSE row.ror END,
      i.country_code = CASE WHEN row.country_code = '' THEN null ELSE row.country_code END
} IN TRANSACTIONS OF 5000 ROWS;

LOAD CSV WITH HEADERS FROM 'file:///topics.csv' AS row
CALL {
  WITH row
  MERGE (t:Topic {topic_id: row.`topic_id:ID(Topic)`})
  SET t.slug = row.slug,
      t.display_name = row.display_name,
      t.kind = row.kind,
      t.source = row.source
} IN TRANSACTIONS OF 5000 ROWS;

LOAD CSV WITH HEADERS FROM 'file:///citations.csv' AS row
CALL {
  WITH row
  MATCH (a:Paper {paper_id: row.`:START_ID(Paper)`}), (b:Paper {paper_id: row.`:END_ID(Paper)`})
  MERGE (a)-[r:CITES]->(b)
  SET r.source = row.source,
      r.is_influential = CASE WHEN row.`is_influential:boolean` = '' THEN null ELSE toBoolean(row.`is_influential:boolean`) END
} IN TRANSACTIONS OF 10000 ROWS;

LOAD CSV WITH HEADERS FROM 'file:///paper_authors.csv' AS row
CALL {
  WITH row
  MATCH (a:Author {author_id: row.`:START_ID(Author)`}), (p:Paper {paper_id: row.`:END_ID(Paper)`})
  MERGE (a)-[r:AUTHORED]->(p)
  SET r.position = toInteger(row.`position:int`),
      r.is_corresponding = toBoolean(row.`is_corresponding:boolean`)
} IN TRANSACTIONS OF 10000 ROWS;

LOAD CSV WITH HEADERS FROM 'file:///author_institutions.csv' AS row
CALL {
  WITH row
  MATCH (a:Author {author_id: row.`:START_ID(Author)`}), (i:Institution {institution_id: row.`:END_ID(Institution)`})
  MERGE (a)-[r:AFFILIATED_WITH]->(i)
  SET r.source = row.source
} IN TRANSACTIONS OF 10000 ROWS;

LOAD CSV WITH HEADERS FROM 'file:///paper_topics.csv' AS row
CALL {
  WITH row
  MATCH (p:Paper {paper_id: row.`:START_ID(Paper)`}), (t:Topic {topic_id: row.`:END_ID(Topic)`})
  MERGE (p)-[r:HAS_TOPIC]->(t)
  SET r.score = CASE WHEN row.`score:float` = '' THEN null ELSE toFloat(row.`score:float`) END,
      r.assignment_source = row.assignment_source
} IN TRANSACTIONS OF 10000 ROWS;

CREATE INDEX paper_openalex IF NOT EXISTS FOR (p:Paper) ON (p.openalex_id);
CREATE INDEX paper_doi IF NOT EXISTS FOR (p:Paper) ON (p.doi);
CREATE INDEX topic_slug IF NOT EXISTS FOR (t:Topic) ON (t.slug);
CREATE INDEX author_name IF NOT EXISTS FOR (a:Author) ON (a.display_name);
