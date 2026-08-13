"use client";

import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  CircleHelp,
  Copy,
  Download,
  ExternalLink,
  Focus,
  GitBranch,
  History,
  Layers3,
  Maximize2,
  Minimize2,
  Network,
  RotateCcw,
  Search,
  SlidersHorizontal,
  Table2,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent, type WheelEvent } from "react";

import type { EvidenceLink, GapAnalysis } from "@/lib/api";

import styles from "./EvidenceWorkspace.module.css";

type WorkspaceView = "matrix" | "map";
type NodeKind = "question" | "cluster" | "paper" | "claim" | "status" | "gap";

type MapNode = {
  id: string;
  kind: NodeKind;
  title: string;
  eyebrow: string;
  x: number;
  y: number;
  width: number;
  height: number;
  paperId?: string;
  claimId?: string;
  status?: string;
};

type MapEdge = {
  id: string;
  from: string;
  to: string;
  active: boolean;
};

type HistoryItem = {
  id: string;
  status: string;
  gap_candidates: string | null;
  search_strategy: string;
  created_at: string;
};

type EvidenceWorkspaceProps = {
  analysis: GapAnalysis;
  history: HistoryItem[];
};

type GraphModel = {
  width: number;
  height: number;
  nodes: MapNode[];
  edges: MapEdge[];
  papers: Map<string, EvidenceLink>;
  adjacency: Map<string, Set<string>>;
};

const COLUMN_X = {
  question: 70,
  cluster: 330,
  paper: 625,
  claim: 950,
  status: 1280,
  gap: 1530,
} as const;

const NODE_WIDTH = {
  question: 210,
  cluster: 210,
  paper: 245,
  claim: 260,
  status: 205,
  gap: 245,
} as const;

const NODE_HEIGHT = {
  question: 112,
  cluster: 82,
  paper: 104,
  claim: 116,
  status: 92,
  gap: 130,
} as const;

const MAP_WIDTH = 1845;
const MAP_VIEWPORT_WIDTH = 1380;
const MAP_VIEWPORT_HEIGHT = 760;

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function distributeY(count: number, height: number, top = 90, bottom = 90) {
  if (count <= 1) return [height / 2];
  const available = height - top - bottom;
  return Array.from({ length: count }, (_, index) => top + (available * index) / (count - 1));
}

function wrapLabel(value: string, maxChars: number, maxLines: number) {
  const clean = value.replace(/\s+/g, " ").trim();
  const words = clean.split(" ");
  const lines: string[] = [];
  let current = "";

  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length <= maxChars) {
      current = candidate;
      continue;
    }
    if (current) lines.push(current);
    current = word;
    if (lines.length === maxLines - 1) break;
  }

  if (current && lines.length < maxLines) lines.push(current);
  if (lines.join(" ").length < clean.length && lines.length) {
    lines[lines.length - 1] = `${lines[lines.length - 1].replace(/[.,;:]$/, "")}…`;
  }
  return lines.slice(0, maxLines);
}

function nodePalette(node: MapNode) {
  if (node.kind === "question") return { fill: "#17211d", stroke: "#17211d", text: "#ffffff", sub: "#cbd7d1" };
  if (node.kind === "cluster") return { fill: "#edf5f1", stroke: "#8db5a5", text: "#17211d", sub: "#477160" };
  if (node.kind === "paper") return { fill: "#ffffff", stroke: "#cbd5ce", text: "#17211d", sub: "#67736d" };
  if (node.kind === "claim") {
    if (node.status === "contradicted" || node.status === "mixed") return { fill: "#f8ece9", stroke: "#d2a097", text: "#542a25", sub: "#8a3c32" };
    if (node.status === "supported") return { fill: "#e4f0ea", stroke: "#8db5a5", text: "#173d2f", sub: "#1d5d45" };
    return { fill: "#f6efe5", stroke: "#d5b58a", text: "#4f3920", sub: "#8a5a1f" };
  }
  if (node.kind === "status") {
    if (node.status === "supported") return { fill: "#dbeae3", stroke: "#7da993", text: "#173d2f", sub: "#1d5d45" };
    if (node.status === "conflict") return { fill: "#f3e1dd", stroke: "#c89187", text: "#542a25", sub: "#8a3c32" };
    return { fill: "#f2eadf", stroke: "#d1ad7c", text: "#4f3920", sub: "#8a5a1f" };
  }
  return { fill: "#19251f", stroke: "#4c6b5e", text: "#ffffff", sub: "#c5d6ce" };
}

function buildGraph(analysis: GapAnalysis): GraphModel {
  const papers = new Map<string, EvidenceLink>();
  for (const claim of analysis.evidence_claims) {
    for (const evidence of claim.evidence) papers.set(evidence.paper_id, evidence);
  }

  const knownPaperIds = new Set(papers.keys());
  const sourceClusters = analysis.evidence_clusters
    .map((cluster) => ({ ...cluster, paper_ids: cluster.paper_ids.filter((paperId) => knownPaperIds.has(paperId)) }))
    .filter((cluster) => cluster.paper_ids.length > 0);
  const clusteredPaperIds = new Set(sourceClusters.flatMap((cluster) => cluster.paper_ids));
  const unclusteredPaperIds = [...knownPaperIds].filter((paperId) => !clusteredPaperIds.has(paperId));
  const clusters = unclusteredPaperIds.length
    ? [...sourceClusters, { slug: "unclassified-evidence", display_name: "Unclassified evidence", paper_ids: unclusteredPaperIds }]
    : sourceClusters;

  const maxColumn = Math.max(clusters.length, papers.size, analysis.evidence_claims.length, 3);
  const height = clamp(maxColumn * 115 + 160, 760, 1500);
  const clusterY = distributeY(clusters.length, height);
  const paperY = distributeY(papers.size, height);
  const claimY = distributeY(analysis.evidence_claims.length, height);
  const statusY = distributeY(3, height, 160, 160);

  const nodes: MapNode[] = [
    {
      id: "question",
      kind: "question",
      title: analysis.research_question,
      eyebrow: "Research question",
      x: COLUMN_X.question,
      y: height / 2,
      width: NODE_WIDTH.question,
      height: NODE_HEIGHT.question,
    },
  ];

  clusters.forEach((cluster, index) => {
    nodes.push({
      id: `cluster:${cluster.slug}`,
      kind: "cluster",
      title: cluster.display_name,
      eyebrow: `${cluster.paper_ids.length} linked paper${cluster.paper_ids.length === 1 ? "" : "s"}`,
      x: COLUMN_X.cluster,
      y: clusterY[index],
      width: NODE_WIDTH.cluster,
      height: NODE_HEIGHT.cluster,
    });
  });

  [...papers.values()].forEach((paper, index) => {
    nodes.push({
      id: `paper:${paper.paper_id}`,
      kind: "paper",
      title: paper.paper_title,
      eyebrow: [paper.publication_year, paper.venue_name].filter(Boolean).join(" · ") || "Evidence paper",
      x: COLUMN_X.paper,
      y: paperY[index],
      width: NODE_WIDTH.paper,
      height: NODE_HEIGHT.paper,
      paperId: paper.paper_id,
    });
  });

  analysis.evidence_claims.forEach((claim, index) => {
    nodes.push({
      id: `claim:${claim.id}`,
      kind: "claim",
      title: claim.claim_text,
      eyebrow: claim.claim_kind.replaceAll("_", " "),
      x: COLUMN_X.claim,
      y: claimY[index],
      width: NODE_WIDTH.claim,
      height: NODE_HEIGHT.claim,
      claimId: claim.id,
      status: claim.support_status,
    });
  });

  const supportedCount = analysis.evidence_claims.filter((claim) => claim.support_status === "supported").length;
  const conflictCount = analysis.evidence_claims.filter((claim) => claim.support_status === "mixed" || claim.support_status === "contradicted").length;
  const insufficientCount = analysis.evidence_claims.filter((claim) => claim.support_status === "insufficient_evidence").length;
  const statusNodes: MapNode[] = [
    {
      id: "status:agreement",
      kind: "status",
      title: supportedCount ? `${supportedCount} supported claim${supportedCount === 1 ? "" : "s"}` : "No established agreement",
      eyebrow: "Agreement",
      x: COLUMN_X.status,
      y: statusY[0],
      width: NODE_WIDTH.status,
      height: NODE_HEIGHT.status,
      status: "supported",
    },
    {
      id: "status:conflict",
      kind: "status",
      title: conflictCount ? `${conflictCount} mixed / contradicted claim${conflictCount === 1 ? "" : "s"}` : "No established conflict",
      eyebrow: "Conflict check",
      x: COLUMN_X.status,
      y: statusY[1],
      width: NODE_WIDTH.status,
      height: NODE_HEIGHT.status,
      status: "conflict",
    },
    {
      id: "status:insufficient",
      kind: "status",
      title: insufficientCount ? `${insufficientCount} claim${insufficientCount === 1 ? "" : "s"} need more evidence` : "No unresolved claims",
      eyebrow: "Insufficient evidence",
      x: COLUMN_X.status,
      y: statusY[2],
      width: NODE_WIDTH.status,
      height: NODE_HEIGHT.status,
      status: "insufficient_evidence",
    },
  ];
  nodes.push(...statusNodes);

  nodes.push({
    id: "gap:candidate",
    kind: "gap",
    title: analysis.candidate_gap?.hypothesis ?? analysis.gap_candidates ?? "Candidate hypothesis requires formulation.",
    eyebrow: "Candidate hypothesis · needs falsification",
    x: COLUMN_X.gap,
    y: height / 2,
    width: NODE_WIDTH.gap,
    height: NODE_HEIGHT.gap,
    status: "insufficient_evidence",
  });

  const edges: MapEdge[] = [];
  const pushEdge = (from: string, to: string, active = true) => {
    edges.push({ id: `${from}->${to}`, from, to, active });
  };

  for (const cluster of clusters) {
    const clusterId = `cluster:${cluster.slug}`;
    pushEdge("question", clusterId);
    for (const paperId of cluster.paper_ids) pushEdge(clusterId, `paper:${paperId}`);
  }

  for (const claim of analysis.evidence_claims) {
    const claimId = `claim:${claim.id}`;
    if (claim.evidence.length) {
      for (const evidence of claim.evidence) pushEdge(`paper:${evidence.paper_id}`, claimId);
    } else {
      pushEdge("question", claimId);
    }
    if (claim.support_status === "supported") pushEdge(claimId, "status:agreement");
    else if (claim.support_status === "mixed" || claim.support_status === "contradicted") pushEdge(claimId, "status:conflict");
    else pushEdge(claimId, "status:insufficient");
  }

  pushEdge("status:agreement", "gap:candidate", supportedCount > 0);
  pushEdge("status:conflict", "gap:candidate", conflictCount > 0);
  pushEdge("status:insufficient", "gap:candidate", insufficientCount > 0);

  const adjacency = new Map<string, Set<string>>();
  for (const edge of edges) {
    if (!adjacency.has(edge.from)) adjacency.set(edge.from, new Set());
    if (!adjacency.has(edge.to)) adjacency.set(edge.to, new Set());
    adjacency.get(edge.from)?.add(edge.to);
    adjacency.get(edge.to)?.add(edge.from);
  }

  return { width: MAP_WIDTH, height, nodes, edges, papers, adjacency };
}

function getStageState(analysis: GapAnalysis) {
  const paperCount = new Set(analysis.evidence_claims.flatMap((claim) => claim.evidence.map((item) => item.paper_id))).size;
  const paperClaimCount = analysis.evidence_claims.filter((claim) => claim.claim_kind === "paper_claim").length;
  const citationCount = analysis.citation_neighborhood.unique_candidate_count;
  return [
    { label: "Retrieving literature", detail: paperCount ? `${paperCount} evidence-linked papers` : "No linked papers", state: paperCount ? "complete" : "pending" },
    {
      label: "Expanding citation neighborhood",
      detail: analysis.citation_neighborhood.seed_paper_count
        ? `${citationCount} local neighbors found · unscreened`
        : "No evidence seeds available",
      state: analysis.citation_neighborhood.seed_paper_count ? "review" : "pending",
    },
    { label: "Grouping evidence", detail: analysis.evidence_clusters.length ? `${analysis.evidence_clusters.length} research axes` : "No axis links yet", state: analysis.evidence_clusters.length ? "complete" : "pending" },
    { label: "Checking agreement / conflict", detail: paperClaimCount ? `${paperClaimCount} paper-backed claims ready for review` : "Needs paper-claim extraction", state: paperClaimCount ? "review" : "pending" },
    { label: "Testing candidate gaps", detail: "Needs falsification", state: "falsify" },
  ];
}

export default function EvidenceWorkspace({ analysis, history }: EvidenceWorkspaceProps) {
  const [view, setView] = useState<WorkspaceView>("map");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [originFilter, setOriginFilter] = useState("all");
  const [supportFilter, setSupportFilter] = useState("all");
  const [isExpanded, setIsExpanded] = useState(false);
  const svgRef = useRef<SVGSVGElement>(null);
  const dragRef = useRef<{ pointerId: number; x: number; y: number; originX: number; originY: number } | null>(null);
  const graph = useMemo(() => buildGraph(analysis), [analysis]);
  const initialScale = clamp(Math.min(0.8, 700 / graph.height), 0.5, 0.8);
  const [viewport, setViewport] = useState({ scale: initialScale, x: 18, y: 18 });
  const stages = useMemo(() => getStageState(analysis), [analysis]);

  useEffect(() => {
    if (!isExpanded) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsExpanded(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isExpanded]);

  const normalizedSearch = searchQuery.trim().toLowerCase();
  const filterActive = Boolean(normalizedSearch || originFilter !== "all" || supportFilter !== "all");
  const filteredClaims = useMemo(() => analysis.evidence_claims.filter((claim) => {
    if (originFilter !== "all" && claim.claim_kind !== originFilter) return false;
    if (supportFilter !== "all" && claim.support_status !== supportFilter) return false;
    if (!normalizedSearch) return true;
    return claim.claim_text.toLowerCase().includes(normalizedSearch)
      || claim.evidence.some((evidence) => evidence.paper_title.toLowerCase().includes(normalizedSearch));
  }), [analysis.evidence_claims, normalizedSearch, originFilter, supportFilter]);

  const filteredNodeIds = useMemo(() => {
    if (!filterActive) return null;
    const ids = new Set<string>(["question", "gap:candidate"]);
    const visibleClaimIds = new Set(filteredClaims.map((claim) => claim.id));
    const visiblePaperIds = new Set<string>();
    for (const claim of filteredClaims) {
      ids.add(`claim:${claim.id}`);
      for (const evidence of claim.evidence) visiblePaperIds.add(evidence.paper_id);
      if (claim.support_status === "supported") ids.add("status:agreement");
      else if (claim.support_status === "mixed" || claim.support_status === "contradicted") ids.add("status:conflict");
      else ids.add("status:insufficient");
    }
    if (normalizedSearch) {
      for (const paper of graph.papers.values()) {
        if (paper.paper_title.toLowerCase().includes(normalizedSearch)) visiblePaperIds.add(paper.paper_id);
      }
    }
    for (const paperId of visiblePaperIds) ids.add(`paper:${paperId}`);
    for (const cluster of analysis.evidence_clusters) {
      if (
        cluster.paper_ids.some((paperId) => visiblePaperIds.has(paperId))
        || (normalizedSearch && cluster.display_name.toLowerCase().includes(normalizedSearch))
      ) {
        ids.add(`cluster:${cluster.slug}`);
      }
    }
    if (normalizedSearch && analysis.research_question.toLowerCase().includes(normalizedSearch)) ids.add("question");
    if (normalizedSearch && (analysis.candidate_gap?.hypothesis ?? "").toLowerCase().includes(normalizedSearch)) ids.add("gap:candidate");
    for (const claimId of visibleClaimIds) ids.add(`claim:${claimId}`);
    return ids;
  }, [analysis.candidate_gap?.hypothesis, analysis.evidence_clusters, analysis.research_question, filterActive, filteredClaims, graph.papers, normalizedSearch]);

  const selectedNode = selectedNodeId ? graph.nodes.find((node) => node.id === selectedNodeId) ?? null : null;
  const relatedNodeIds = useMemo(() => {
    if (!selectedNodeId) return null;
    return new Set([selectedNodeId, ...(graph.adjacency.get(selectedNodeId) ?? [])]);
  }, [graph.adjacency, selectedNodeId]);

  const selectedPaper = selectedNode?.paperId ? graph.papers.get(selectedNode.paperId) ?? null : null;
  const selectedPaperClaims = selectedPaper
    ? analysis.evidence_claims.filter((claim) => claim.evidence.some((evidence) => evidence.paper_id === selectedPaper.paper_id))
    : [];
  const selectedClaim = selectedNode?.claimId
    ? analysis.evidence_claims.find((claim) => claim.id === selectedNode.claimId) ?? null
    : null;
  const selectedClaimEvidence = selectedClaim?.evidence[0] ?? null;
  const selectedCluster = selectedNode?.kind === "cluster"
    ? analysis.evidence_clusters.find((cluster) => selectedNode.id === `cluster:${cluster.slug}`) ?? null
    : null;

  const resetViewport = () => setViewport({ scale: initialScale, x: 18, y: 18 });
  const zoomBy = (delta: number) => setViewport((current) => ({ ...current, scale: clamp(current.scale + delta, 0.48, 1.65) }));

  const clientToSvgPoint = (svg: SVGSVGElement, clientX: number, clientY: number) => {
    const matrix = svg.getScreenCTM();
    if (!matrix) return { x: clientX, y: clientY };
    const point = new DOMPoint(clientX, clientY).matrixTransform(matrix.inverse());
    return { x: point.x, y: point.y };
  };

  const handleWheel = (event: WheelEvent<SVGSVGElement>) => {
    event.preventDefault();
    const pointer = clientToSvgPoint(event.currentTarget, event.clientX, event.clientY);
    setViewport((current) => {
      const nextScale = clamp(current.scale + (event.deltaY < 0 ? 0.08 : -0.08), 0.48, 1.65);
      const ratio = nextScale / current.scale;
      return {
        scale: nextScale,
        x: pointer.x - (pointer.x - current.x) * ratio,
        y: pointer.y - (pointer.y - current.y) * ratio,
      };
    });
  };

  const handlePointerDown = (event: ReactPointerEvent<SVGSVGElement>) => {
    const target = event.target as Element;
    if (target.closest("[data-map-node]")) return;
    const pointer = clientToSvgPoint(event.currentTarget, event.clientX, event.clientY);
    dragRef.current = { pointerId: event.pointerId, x: pointer.x, y: pointer.y, originX: viewport.x, originY: viewport.y };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handlePointerMove = (event: ReactPointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const pointer = clientToSvgPoint(event.currentTarget, event.clientX, event.clientY);
    setViewport((current) => ({ ...current, x: drag.originX + pointer.x - drag.x, y: drag.originY + pointer.y - drag.y }));
  };

  const handlePointerEnd = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (dragRef.current?.pointerId === event.pointerId) dragRef.current = null;
  };

  const serializeMap = () => {
    if (!svgRef.current) return null;
    const clone = svgRef.current.cloneNode(true) as SVGSVGElement;
    clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    clone.setAttribute("width", String(graph.width));
    clone.setAttribute("height", String(graph.height));
    clone.setAttribute("viewBox", `0 0 ${graph.width} ${graph.height}`);
    const root = clone.querySelector("[data-export-root]");
    root?.setAttribute("transform", "translate(0 0) scale(1)");
    return new XMLSerializer().serializeToString(clone);
  };

  const downloadSvg = () => {
    const serialized = serializeMap();
    if (!serialized) return;
    const blob = new Blob([serialized], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `evidence-map-${analysis.id.slice(0, 8)}.svg`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const downloadPng = () => {
    const serialized = serializeMap();
    if (!serialized) return;
    const blob = new Blob([serialized], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const image = new Image();
    image.onload = () => {
      const scale = 1.5;
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(graph.width * scale);
      canvas.height = Math.round(graph.height * scale);
      const context = canvas.getContext("2d");
      if (!context) return;
      context.fillStyle = "#f7f7f2";
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.scale(scale, scale);
      context.drawImage(image, 0, 0, graph.width, graph.height);
      const anchor = document.createElement("a");
      anchor.href = canvas.toDataURL("image/png");
      anchor.download = `evidence-map-${analysis.id.slice(0, 8)}.png`;
      anchor.click();
      URL.revokeObjectURL(url);
    };
    image.onerror = () => URL.revokeObjectURL(url);
    image.src = url;
  };

  const renderInspector = () => {
    if (!selectedNode) {
      return (
        <div className={styles.inspectorBody}>
          <div className={styles.inspectorHeader}>
            <div>
              <span className={styles.inspectorKicker}>Falsification queue</span>
              <h4>Pressure-test what the current map has not ruled out.</h4>
            </div>
            <Focus size={18} />
          </div>
          <div className={styles.queueStats}>
            <div><strong>{analysis.citation_neighborhood.unique_candidate_count}</strong><span>local citation neighbors</span></div>
            <div><strong>{analysis.evidence_claims.filter((claim) => claim.claim_kind === "paper_claim").length}</strong><span>paper-backed claims</span></div>
            <div><strong>{analysis.evidence_claims.filter((claim) => claim.support_status === "insufficient_evidence").length}</strong><span>unresolved claims</span></div>
          </div>
          <div className={styles.warningPanel}>
            <AlertTriangle size={16} />
            <span>Citation neighbors are discovery candidates only. They do not become evidence until relevance and source support are reviewed.</span>
          </div>
          {analysis.candidate_gap && (
            <div className={styles.excerptBlock}>
              <span>Next falsification query</span>
              <code>{analysis.candidate_gap.next_search_query}</code>
              <button
                type="button"
                className={styles.copyButton}
                onClick={() => navigator.clipboard.writeText(analysis.candidate_gap?.next_search_query ?? "")}
              >
                <Copy size={13} /> Copy query
              </button>
            </div>
          )}
          <div className={styles.linkedEvidenceList}>
            <span>Local citation candidates</span>
            {analysis.citation_neighborhood.candidates.length ? analysis.citation_neighborhood.candidates.slice(0, 8).map((candidate) => (
              <Link key={candidate.paper_id} href={`/library/${candidate.paper_id}`} className={styles.citationCandidate}>
                <GitBranch size={14} />
                <span>
                  <strong>{candidate.title}</strong>
                  <small>{candidate.publication_year ?? "Year unknown"} · {candidate.direction} · linked to {candidate.linked_seed_count} seed{candidate.linked_seed_count === 1 ? "" : "s"}</small>
                </span>
                <ArrowRight size={13} />
              </Link>
            )) : <p>No locally resolved citation neighbors are available for the current evidence set.</p>}
          </div>
          <p className={styles.inspectorHint}>Select any map or matrix node to replace this queue with its evidence detail.</p>
        </div>
      );
    }

    if (selectedPaper) {
      return (
        <div className={styles.inspectorBody}>
          <div className={styles.inspectorHeader}>
            <div><span className={styles.inspectorKicker}>Evidence paper</span><h4>{selectedPaper.paper_title}</h4></div>
            <button type="button" className={styles.iconButton} onClick={() => setSelectedNodeId(null)} aria-label="Close inspector"><X size={16} /></button>
          </div>
          <dl className={styles.detailList}>
            <div><dt>Year</dt><dd>{selectedPaper.publication_year ?? "Not recorded"}</dd></div>
            <div><dt>Venue</dt><dd>{selectedPaper.venue_name ?? "Not recorded"}</dd></div>
            <div><dt>Source locator</dt><dd>{selectedPaper.source_locator ?? "Metadata / abstract evidence"}</dd></div>
            <div><dt>Relation</dt><dd>{selectedPaper.relation}</dd></div>
            <div><dt>Linked claims</dt><dd>{selectedPaperClaims.length}</dd></div>
          </dl>
          <div className={styles.excerptBlock}>
            <span>Evidence excerpt</span>
            <p>{selectedPaper.excerpt ?? "No chunk or abstract excerpt is stored for this evidence link."}</p>
          </div>
          {(selectedPaper.primary_url || selectedPaper.doi) && (
            <a className={styles.sourceButton} href={selectedPaper.primary_url ?? `https://doi.org/${selectedPaper.doi}`} target="_blank" rel="noreferrer">
              Open source <ExternalLink size={14} />
            </a>
          )}
          <div className={styles.linkedEvidenceList}>
            <span>Claim origin / support</span>
            {selectedPaperClaims.map((claim) => (
              <button key={claim.id} type="button" onClick={() => setSelectedNodeId(`claim:${claim.id}`)}>
                <GitBranch size={14} />
                <span>{claim.claim_kind.replaceAll("_", " ")} · {claim.support_status.replaceAll("_", " ")}<br />{claim.claim_text}</span>
              </button>
            ))}
          </div>
        </div>
      );
    }

    if (selectedClaim) {
      return (
        <div className={styles.inspectorBody}>
          <div className={styles.inspectorHeader}>
            <div><span className={styles.inspectorKicker}>Claim</span><h4>{selectedClaim.claim_text}</h4></div>
            <button type="button" className={styles.iconButton} onClick={() => setSelectedNodeId(null)} aria-label="Close inspector"><X size={16} /></button>
          </div>
          <dl className={styles.detailList}>
            <div><dt>Support status</dt><dd><span className={`${styles.statusPill} ${styles[`status_${selectedClaim.support_status}`] ?? ""}`}>{selectedClaim.support_status.replaceAll("_", " ")}</span></dd></div>
            <div><dt>Claim origin</dt><dd>{selectedClaim.claim_kind.replaceAll("_", " ")}</dd></div>
            <div><dt>Evidence links</dt><dd>{selectedClaim.evidence.length}</dd></div>
            <div><dt>Paper year</dt><dd>{selectedClaimEvidence?.publication_year ?? "No linked paper"}</dd></div>
            <div><dt>Venue</dt><dd>{selectedClaimEvidence?.venue_name ?? "No linked paper"}</dd></div>
            <div><dt>Source locator</dt><dd>{selectedClaimEvidence?.source_locator ?? "No direct locator"}</dd></div>
          </dl>
          <div className={styles.excerptBlock}>
            <span>Evidence excerpt</span>
            <p>{selectedClaimEvidence?.excerpt ?? "No paper excerpt is directly linked to this claim."}</p>
          </div>
          <div className={styles.linkedEvidenceList}>
            <span>Linked evidence</span>
            {selectedClaim.evidence.length ? selectedClaim.evidence.map((evidence) => (
              <button key={evidence.paper_id} type="button" onClick={() => setSelectedNodeId(`paper:${evidence.paper_id}`)}>
                <BookOpen size={14} /><span>{evidence.paper_title}</span>
              </button>
            )) : <p>No paper evidence is directly linked to this claim.</p>}
          </div>
        </div>
      );
    }

    if (selectedCluster) {
      return (
        <div className={styles.inspectorBody}>
          <div className={styles.inspectorHeader}>
            <div><span className={styles.inspectorKicker}>Evidence cluster</span><h4>{selectedCluster.display_name}</h4></div>
            <button type="button" className={styles.iconButton} onClick={() => setSelectedNodeId(null)} aria-label="Close inspector"><X size={16} /></button>
          </div>
          <p className={styles.inspectorCopy}>This cluster is based on stored research-axis assignments for evidence-linked papers. It is not a claim that the field itself is organized this way.</p>
          <div className={styles.linkedEvidenceList}>
            <span>{selectedCluster.paper_ids.length} linked papers</span>
            {selectedCluster.paper_ids.map((paperId) => {
              const paper = graph.papers.get(paperId);
              if (!paper) return null;
              return <button key={paperId} type="button" onClick={() => setSelectedNodeId(`paper:${paperId}`)}><BookOpen size={14} /><span>{paper.paper_title}</span></button>;
            })}
          </div>
        </div>
      );
    }

    return (
      <div className={styles.inspectorBody}>
        <div className={styles.inspectorHeader}>
          <div><span className={styles.inspectorKicker}>{selectedNode.eyebrow}</span><h4>{selectedNode.title}</h4></div>
          <button type="button" className={styles.iconButton} onClick={() => setSelectedNodeId(null)} aria-label="Close inspector"><X size={16} /></button>
        </div>
        {selectedNode.kind === "question" && <p className={styles.inspectorCopy}>{analysis.search_strategy}</p>}
        {selectedNode.kind === "status" && <p className={styles.inspectorCopy}>This node summarizes claim support states recorded in this canvas. It does not infer field-wide consensus from retrieval density.</p>}
        {selectedNode.kind === "gap" && analysis.candidate_gap && (
          <>
            <div className={styles.warningPanel}><AlertTriangle size={16} /><span>Candidate hypothesis only. It remains insufficient evidence until broader search and falsification checks are performed.</span></div>
            <dl className={styles.detailList}>
              <div><dt>Support status</dt><dd>{analysis.candidate_gap.support_status.replaceAll("_", " ")}</dd></div>
              <div><dt>Falsification</dt><dd>{analysis.candidate_gap.falsifiability_note}</dd></div>
            </dl>
            <div className={styles.excerptBlock}><span>Next search query</span><code>{analysis.candidate_gap.next_search_query}</code></div>
          </>
        )}
      </div>
    );
  };

  return (
    <section className={`${styles.workspace} ${isExpanded ? styles.workspaceExpanded : ""}`}>
      <div className={styles.traceHeader}>
        <div>
          <span className={styles.kicker}>Analysis trace</span>
          <h3>What this canvas has actually established</h3>
        </div>
        <span className={styles.scopeBadge}>Evidence-linked scope only</span>
      </div>

      <div className={styles.stageGrid}>
        {stages.map((stage, index) => (
          <div className={styles.stageCard} key={stage.label} data-state={stage.state}>
            <div className={styles.stageTopline}><span>{String(index + 1).padStart(2, "0")}</span>{stage.state === "complete" ? <CheckCircle2 size={15} /> : stage.state === "review" ? <GitBranch size={15} /> : stage.state === "not-recorded" ? <CircleHelp size={15} /> : <Search size={15} />}</div>
            <strong>{stage.label}</strong>
            <small>{stage.detail}</small>
          </div>
        ))}
      </div>

      <div className={styles.workspaceToolbar}>
        <div className={styles.viewTabs} role="tablist" aria-label="Gap canvas view">
          <button type="button" role="tab" aria-selected={view === "matrix"} className={view === "matrix" ? styles.activeTab : ""} onClick={() => setView("matrix")}><Table2 size={16} /> Evidence Matrix</button>
          <button type="button" role="tab" aria-selected={view === "map"} className={view === "map" ? styles.activeTab : ""} onClick={() => setView("map")}><Network size={16} /> Evidence Map</button>
        </div>
        <div className={styles.toolbarActions}>
          {history.length > 1 && (
            <details className={styles.historyMenu}>
              <summary><History size={15} /> History</summary>
              <div className={styles.historyPopover}>
                {history.slice().reverse().slice(0, 8).map((item, index) => (
                  <Link key={item.id} href={`/gap-canvas?id=${item.id}`} className={item.id === analysis.id ? styles.currentHistory : ""}>
                    <span>Pass {history.length - index} · {item.status}</span>
                    <small>{new Date(item.created_at).toLocaleString()}</small>
                    <small>{item.search_strategy}</small>
                  </Link>
                ))}
              </div>
            </details>
          )}
          <details className={styles.helpMenu}>
            <summary><CircleHelp size={15} /> Read the map</summary>
            <div className={styles.helpPopover}>
              <strong>Evidence-first reading order</strong>
              <p>Research axis nodes come from stored paper taxonomy. Paper-to-claim links come from evidence links. Support nodes summarize recorded claim states. Candidate hypotheses remain falsifiable, not discovered facts.</p>
            </div>
          </details>
          <button type="button" className={styles.toolbarButton} onClick={() => setIsExpanded((current) => !current)}>
            {isExpanded ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
            {isExpanded ? "Exit focus" : "Focus mode"}
          </button>
        </div>
      </div>

      <div className={styles.filterToolbar}>
        <label className={styles.searchFilter}>
          <Search size={14} />
          <input
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="Find a paper, claim, or research axis"
            aria-label="Filter evidence map"
          />
        </label>
        <label className={styles.selectFilter}>
          <SlidersHorizontal size={13} />
          <select value={originFilter} onChange={(event) => setOriginFilter(event.target.value)} aria-label="Filter by claim origin">
            <option value="all">All origins</option>
            <option value="paper_claim">Paper claims</option>
            <option value="fact">Facts</option>
            <option value="system_inference">System inferences</option>
            <option value="user_note">User notes</option>
          </select>
        </label>
        <label className={styles.selectFilter}>
          <select value={supportFilter} onChange={(event) => setSupportFilter(event.target.value)} aria-label="Filter by support status">
            <option value="all">All support states</option>
            <option value="supported">Supported</option>
            <option value="mixed">Mixed</option>
            <option value="contradicted">Contradicted</option>
            <option value="insufficient_evidence">Insufficient evidence</option>
          </select>
        </label>
        <span className={styles.filterCount}>
          {filterActive ? `${filteredClaims.length}/${analysis.evidence_claims.length} claims visible` : `${analysis.evidence_claims.length} claims · ${graph.papers.size} papers`}
        </span>
        {filterActive && (
          <button
            type="button"
            className={styles.clearFilters}
            onClick={() => { setSearchQuery(""); setOriginFilter("all"); setSupportFilter("all"); }}
          >
            <X size={13} /> Clear
          </button>
        )}
      </div>

      {view === "matrix" ? (
        <div className={styles.matrixLayout}>
          <div className={styles.matrixScroller}>
            <table className={styles.matrixTable}>
              <thead><tr><th>Claim</th><th>Origin</th><th>Support</th><th>Evidence</th></tr></thead>
              <tbody>
                {filteredClaims.map((claim) => (
                  <tr key={claim.id} onClick={() => setSelectedNodeId(`claim:${claim.id}`)}>
                    <td><strong>{claim.claim_text}</strong></td>
                    <td><span className={styles.originPill}>{claim.claim_kind.replaceAll("_", " ")}</span></td>
                    <td><span className={`${styles.statusPill} ${styles[`status_${claim.support_status}`] ?? ""}`}>{claim.support_status.replaceAll("_", " ")}</span></td>
                    <td>
                      <div className={styles.matrixEvidence}>
                        {claim.evidence.length ? claim.evidence.map((evidence) => (
                          <button key={evidence.paper_id} type="button" onClick={(event) => { event.stopPropagation(); setSelectedNodeId(`paper:${evidence.paper_id}`); }}>{evidence.paper_title}</button>
                        )) : <span>No direct paper link</span>}
                      </div>
                    </td>
                  </tr>
                ))}
                {!filteredClaims.length && (
                  <tr><td colSpan={4}><div className={styles.matrixEmpty}>No claims match the current filters.</div></td></tr>
                )}
              </tbody>
            </table>
          </div>
          <aside className={styles.inspector}>{renderInspector()}</aside>
        </div>
      ) : (
        <div className={styles.mapLayout}>
          <div className={styles.mapShell}>
            <div className={styles.mapControls}>
              <button type="button" onClick={() => zoomBy(0.1)} aria-label="Zoom in"><ZoomIn size={16} /></button>
              <button type="button" onClick={() => zoomBy(-0.1)} aria-label="Zoom out"><ZoomOut size={16} /></button>
              <button type="button" onClick={resetViewport} aria-label="Reset view"><RotateCcw size={16} /></button>
              <span>{Math.round(viewport.scale * 100)}%</span>
            </div>
            <div className={styles.exportControls}>
              <button type="button" onClick={downloadPng}><Download size={14} /> PNG</button>
              <button type="button" onClick={downloadSvg}><Download size={14} /> SVG</button>
            </div>
            <div className={styles.mapGuide}><GitBranch size={14} /> Click a node to isolate its immediate evidence neighborhood. Drag the canvas or use the wheel to navigate.</div>
            <svg
              ref={svgRef}
              className={styles.mapSvg}
              viewBox={`0 0 ${MAP_VIEWPORT_WIDTH} ${MAP_VIEWPORT_HEIGHT}`}
              preserveAspectRatio="xMidYMid meet"
              onWheel={handleWheel}
              onPointerDown={handlePointerDown}
              onPointerMove={handlePointerMove}
              onPointerUp={handlePointerEnd}
              onPointerCancel={handlePointerEnd}
            >
              <rect width={graph.width} height={graph.height} fill="#f7f7f2" />
              <g data-export-root transform={`translate(${viewport.x} ${viewport.y}) scale(${viewport.scale})`}>
                {graph.edges.map((edge) => {
                  const from = graph.nodes.find((node) => node.id === edge.from);
                  const to = graph.nodes.find((node) => node.id === edge.to);
                  if (!from || !to) return null;
                  const fromX = from.x + from.width;
                  const toX = to.x;
                  const control = Math.max(55, (toX - fromX) * 0.48);
                  const isRelated = !relatedNodeIds || (relatedNodeIds.has(edge.from) && relatedNodeIds.has(edge.to));
                  const isFilteredIn = !filteredNodeIds || (filteredNodeIds.has(edge.from) && filteredNodeIds.has(edge.to));
                  const isHighlighted = isRelated && isFilteredIn;
                  return (
                    <path
                      key={edge.id}
                      d={`M ${fromX} ${from.y} C ${fromX + control} ${from.y}, ${toX - control} ${to.y}, ${toX} ${to.y}`}
                      fill="none"
                      stroke={isHighlighted ? (edge.active ? "#879b91" : "#c9cec9") : "#dfe3df"}
                      strokeWidth={isHighlighted ? 1.8 : 1.1}
                      strokeDasharray={edge.active ? undefined : "7 7"}
                      opacity={isHighlighted ? 0.9 : 0.16}
                    />
                  );
                })}
                {graph.nodes.map((node) => {
                  const palette = nodePalette(node);
                  const isRelated = !relatedNodeIds || relatedNodeIds.has(node.id);
                  const isFilteredIn = !filteredNodeIds || filteredNodeIds.has(node.id);
                  const isHighlighted = isRelated && isFilteredIn;
                  const isSelected = selectedNodeId === node.id;
                  const lines = wrapLabel(node.title, node.kind === "paper" || node.kind === "claim" ? 30 : 26, node.kind === "gap" ? 4 : 3);
                  const left = node.x;
                  const top = node.y - node.height / 2;
                  return (
                    <g
                      key={node.id}
                      data-map-node="true"
                      role="button"
                      aria-label={`${node.eyebrow}: ${node.title}`}
                      onClick={(event) => { event.stopPropagation(); setSelectedNodeId((current) => current === node.id ? null : node.id); }}
                      opacity={isHighlighted ? 1 : 0.12}
                      style={{ cursor: "pointer", transition: "opacity 160ms ease" }}
                    >
                      <rect
                        x={left}
                        y={top}
                        width={node.width}
                        height={node.height}
                        rx={node.kind === "question" || node.kind === "gap" ? 22 : 16}
                        fill={palette.fill}
                        stroke={isSelected ? "#0f7a54" : palette.stroke}
                        strokeWidth={isSelected ? 3 : 1.4}
                      />
                      <text x={left + 16} y={top + 24} fill={palette.sub} fontSize="10.5" fontWeight="700" letterSpacing="1.1">{node.eyebrow.toUpperCase()}</text>
                      <text x={left + 16} y={top + 48} fill={palette.text} fontSize={node.kind === "question" || node.kind === "gap" ? "14" : "13"} fontWeight="700">
                        {lines.map((line, index) => <tspan key={`${node.id}-${index}`} x={left + 16} dy={index === 0 ? 0 : 18}>{line}</tspan>)}
                      </text>
                    </g>
                  );
                })}
              </g>
            </svg>
          </div>
          <aside className={styles.inspector}>{renderInspector()}</aside>
        </div>
      )}

      <div className={styles.legendBar}>
        <span><i data-tone="question" /> Research question</span>
        <span><i data-tone="cluster" /> Research axis</span>
        <span><i data-tone="paper" /> Paper</span>
        <span><i data-tone="supported" /> Supported</span>
        <span><i data-tone="conflict" /> Conflict / mixed</span>
        <span><i data-tone="insufficient" /> Insufficient evidence</span>
        <span className={styles.legendNote}><Layers3 size={13} /> Sparse retrieval is a coverage signal, not proof of a gap.</span>
      </div>
    </section>
  );
}
