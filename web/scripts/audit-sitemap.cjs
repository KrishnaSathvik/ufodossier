// Run from web/: node scripts/audit-sitemap.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
function load(file, overrides = {}) {
  const exports = {};
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
  }).outputText;
  vm.runInNewContext(code, { exports, process, require: name => overrides[name] ?? require(name) }, { filename: file });
  return exports;
}
const catalog = load('src/lib/corpus/catalog.ts');
const sources = catalog.listSources();
const official = JSON.parse(fs.readFileSync('../pipeline/snapshots/pursue/2026-09-18-official/records.json'));
const coverage = JSON.parse(fs.readFileSync('../pipeline/reports/corpus_qa/source_coverage.json')).records;
assert.equal(sources.length, coverage.length);
assert.equal(new Set(sources.map(s => s.slug)).size, coverage.length);
for (const source of sources) {
  assert(source.slug && !['null', 'undefined'].includes(source.slug));
  assert.equal(catalog.getSource(source.slug)?.identityKey, source.identityKey);
  const record = official.find(r => (r.identity_key === source.identityKey || (source.externalId && r.identity_key === `pursue:${source.externalId}`)) && r.source_type === source.type);
  assert(record, `Missing official record: ${source.identityKey}`);
  assert.equal(source.originalUrl, record.original_url ?? null);
  if (source.identityKey === `pursue:${source.externalId}`) assert.equal(source.slug, source.externalId);
}
assert.notEqual(catalog.getSource('FBI-UAP-D014').identityKey, catalog.getSource('FBI-UAP-D014-image').identityKey);
assert.equal(catalog.getSource('FBI-UAP-D014').type, 'pdf');
assert.equal(catalog.getSource('FBI-UAP-D014-image').type, 'image');
assert.equal(catalog.fragmentsForSource('FBI-UAP-D014-image').length, 0);
const fragments = catalog.listFragments();
const dbRows = Array.from({length: 201}, (_, i) => ({slug: `database-case-${i}`, extracted_at: null}));
dbRows.push({slug: fragments[0].slug, extracted_at: null});
let failure = null;
function from(table) {
  return {select(){return this},not(){return this},order(){return this},
    range(start,end){return Promise.resolve({data: dbRows.slice(start,end+1), error: failure === table ? {message:'test outage'} : null})},
    then(resolve,reject){return Promise.resolve({data: [{slug:'sample-collection',created_at:null}],error:failure === table ? {message:'test outage'} : null}).then(resolve,reject)}
  };
}
const sitemap = load('src/app/sitemap.ts', {
  '@/lib/corpus/catalog': catalog,
  '@/lib/supabase': {getSupabaseServer: () => ({from})},
}).default;
(async () => {
  const entries = await sitemap();
  const urls = new Set(entries.map(e => e.url));
  assert.equal(entries.length, urls.size);
  for (const source of sources) assert(urls.has(`https://www.ufodossier.com/source/${encodeURIComponent(source.slug)}`));
  for (const fragment of fragments) {
    assert(urls.has(`https://www.ufodossier.com/incident/${encodeURIComponent(fragment.slug)}`));
    assert(catalog.getFragmentBySlug(fragment.slug));
  }
  for (const row of dbRows) assert(urls.has(`https://www.ufodossier.com/incident/${row.slug}`));
  for (const release of catalog.listReleases()) assert(urls.has(`https://www.ufodossier.com/releases/${String(release.release).padStart(2,'0')}`));
  assert(urls.has('https://www.ufodossier.com/collections/sample-collection'));
  for (failure of ['incidents','collections']) await assert.rejects(sitemap, /query failed/);
  const graph = JSON.parse(fs.readFileSync('../pipeline/reports/corpus_qa/linker/full_graph.json'));
  const caseIds = new Set(graph.canonical_events.flatMap(e => e.member_case_ids));
  const localIds = new Set(fragments.map(f => f.caseId));
  const missingLocal = [...caseIds].filter(id => !localIds.has(id));
  console.log(JSON.stringify({sourcePages:sources.length, localIncidentPages:fragments.length, releases:catalog.listReleases().length, stats:catalog.getCorpusStats(), graphCasesNotInLocalCatalog:missingLocal.length},null,2));
  if (process.argv.includes('--database')) {
    require('@next/env').loadEnvConfig(process.cwd());
    const supabase = load('src/lib/supabase.ts');
    const sb = supabase.getSupabaseServer();
    const published = [];
    for (let start = 0; ; start += 200) {
      const {data,error} = await sb.from('incidents').select('case_id,slug').order('id').range(start,start+199);
      if (error) throw error;
      published.push(...data);
      if (data.length < 200) break;
    }
    const liveSitemap = load('src/app/sitemap.ts', {'@/lib/corpus/catalog':catalog,'@/lib/supabase':supabase}).default;
    const result = await liveSitemap();
    const resultUrls = new Set(result.map(e=>e.url));
    const publishedByCase = new Map(published.filter(r=>r.slug).map(r=>[r.case_id.toUpperCase(),r.slug]));
    const uncovered = [...caseIds].filter(id=>!localIds.has(id) && !publishedByCase.has(id.toUpperCase()));
    assert.equal(uncovered.length,0, `Uncovered graph cases: ${uncovered.join(', ')}`);
    for (const row of published.filter(r=>r.slug)) assert(resultUrls.has(`https://www.ufodossier.com/incident/${row.slug}`));
    assert.equal(resultUrls.size,result.length);
    console.log(JSON.stringify({databaseIncidentPages:published.filter(r=>r.slug).length,totalUniqueSitemapUrls:result.length,incidentUrls:result.filter(e=>e.url.includes('/incident/')).length,coveredCheckedPassages:caseIds.size,coveredSightings:graph.canonical_events.length,uncoveredPassages:uncovered.length},null,2));
  }
  console.log('PASS: unique source routes and correct metadata, full local sitemap coverage, database pagination, deduplication, and query failure handling.');
})().catch(error => {console.error(error);process.exitCode=1});
