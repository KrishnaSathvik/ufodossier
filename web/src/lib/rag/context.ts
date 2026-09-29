import type { FragmentRecord, SourceRecord } from "@/lib/corpus/catalog";
import type { CanonicalContext, RetrievedFile, RetrievedIncident } from "./types";

export function formatFacts(cases: FragmentRecord[], files: SourceRecord[], mapPoints: number): string {
  const counted = files.filter((file) => file.externalId);
  const ofType = (type: string) => counted.filter((file) => file.type === type).length;
  return [
    `Cases: ${cases.length}`,
    `Released files: ${counted.length}`,
    `Documents: ${ofType("pdf")}`,
    `Audio recordings: ${ofType("audio")}`,
    `Videos: ${ofType("video")}`,
    `Images: ${ofType("image")}`,
    `Map points: ${mapPoints}`,
  ].join("\n");
}

export function formatFileLines(files: SourceRecord[]): string {
  return files
    .filter((file) => file.externalId)
    .map((file) => `${file.externalId} | ${file.type} | ${file.agency} | ${file.title}`)
    .join("\n");
}

export function buildUserMessage(
  question: string,
  incidents: RetrievedIncident[],
  files: RetrievedFile[] = [],
  facts = "",
  scopedFiles = "",
  note = "",
): string {
  const cases = incidents.length
    ? incidents.map((incident) => formatIncident(incident)).join("\n\n---\n\n")
    : "None.";
  const fileBlock = files.length
    ? files.map((file) => formatFile(file)).join("\n\n---\n\n")
    : "None.";
  const scoped = scopedFiles
    ? `\nFiles of the kind this question asks about:\n${scopedFiles}\n`
    : "";

  return `Question: ${question}

Archive counts:
${facts || "None."}
${scoped}
Records found for this question:
${note ? `${note}\n` : ""}${cases}

Files found for this question:
${fileBlock}

Answer from this archive only. Cite a case id in brackets when you use that case. Name a released file by its title, not in brackets.`;
}

function formatIncident(incident: RetrievedIncident): string {
  const lines = [
    `CASE ${incident.case_id}`,
    `Title: ${incident.title}`,
    `Date: ${incident.occurred_at ?? "undated"}`,
    `Location: ${incident.location_text ?? "not stated"}`,
    `Agency or branch: ${incident.branch ?? "not stated"}`,
    `Status in the file: ${incident.resolution_status ?? "not stated"}`,
    `Summary: ${incident.summary}`,
    `Verbatim excerpt: "${incident.raw_excerpt}"`,
  ];
  if (incident.identity) {
    lines.push(formatIdentity(incident.identity));
  }
  return lines.join("\n");
}

function formatFile(file: RetrievedFile): string {
  return [
    `File ${file.id}`,
    `Title: ${file.title}`,
    `Kind: ${file.kind}`,
    `Agency: ${file.agency}`,
    `Note: ${file.note ?? "none"}`,
    "This is a released file, not a case id.",
  ].join("\n");
}

function formatIdentity(identity: CanonicalContext): string {
  const lines = [`Sighting: ${identity.eventLabel}`];
  if (identity.memberCaseIds.length > 1) {
    lines.push(`Also written up as: ${identity.memberCaseIds.join(", ")}`);
  }
  if (identity.seriesLabel && identity.seriesEventCount) {
    lines.push(`Part of ${identity.seriesLabel}, a group of ${identity.seriesEventCount} separate sightings.`);
  }
  return lines.join("\n");
}
