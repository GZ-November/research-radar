"""Extract Research Radar SQLite data into a frontend seed JSON (read-only)."""
import sqlite3, json, pathlib

DB = "/Users/georgezhu/Desktop/InkMind Agent DEMO/data/research_radar.db"
OUT = pathlib.Path("/Users/georgezhu/Desktop/InkMind Agent DEMO/research-radar-web/src/data/seed.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

def rows(q, args=()):
    return [dict(r) for r in conn.execute(q, args)]

def parse_json_fields(rec, fields):
    for f in fields:
        v = rec.get(f)
        if isinstance(v, str) and v.strip():
            try:
                rec[f.replace("_json", "")] = json.loads(v)
            except Exception:
                pass
        rec.pop(f, None)
    return rec

cases_out = []
for case in rows("SELECT * FROM research_cases ORDER BY created_at"):
    cid = case["id"]
    settings = parse_json_fields(case, ["settings_json"])
    is_demo = cid == "case-demo-radar" or "fixture_dir" in (settings.get("settings") or {})

    versions = rows(
        "SELECT id, version_no, file_name, source_type, is_current, created_at "
        "FROM manuscript_versions WHERE case_id=? ORDER BY version_no", (cid,))
    current_vid = next((v["id"] for v in versions if v["is_current"]), None)

    claims = []
    for cl in rows("SELECT * FROM claims WHERE case_id=?", (cid,)):
        revs = rows("SELECT * FROM claim_revisions WHERE claim_id=? ORDER BY revision_no", (cl["id"],))
        for r in revs:
            parse_json_fields(r, ["contract_json"])
            r["is_current_version"] = r["manuscript_version_id"] == current_vid
        claims.append({
            "id": cl["id"], "stable_key": cl["stable_key"],
            "lifecycle_state": cl["lifecycle_state"], "revisions": revs,
        })

    scans = rows("SELECT * FROM scan_runs WHERE case_id=? ORDER BY created_at DESC", (cid,))
    for s in scans:
        parse_json_fields(s, ["query_json", "stats_json"])
    latest_scan = next((s for s in scans if s["status"] == "completed"), scans[0] if scans else None)

    impacts = []
    if latest_scan:
        for ic in rows("SELECT * FROM impact_candidates WHERE scan_run_id=?", (latest_scan["id"],)):
            parse_json_fields(ic, ["strategic_flags_json", "condition_differences_json",
                                   "evidence_own_json", "evidence_new_json", "uncertainty_json"])
            snap = conn.execute("SELECT * FROM source_snapshots WHERE id=?",
                                (ic["source_snapshot_id"],)).fetchone()
            src = None
            if snap:
                snap = dict(snap)
                srow = conn.execute("SELECT * FROM sources WHERE id=?", (snap["source_id"],)).fetchone()
                if srow:
                    src = parse_json_fields(dict(srow), ["authors_json"])
            # attach claim stable_key + statement
            rev = conn.execute(
                "SELECT cr.statement, c.stable_key FROM claim_revisions cr "
                "JOIN claims c ON c.id = cr.claim_id WHERE cr.id=?",
                (ic["claim_revision_id"],)).fetchone()
            ic["claim_stable_key"] = rev["stable_key"] if rev else None
            ic["claim_statement"] = rev["statement"] if rev else None
            ic["source"] = src
            ic["source_snapshot_abstract"] = (snap or {}).get("abstract") if snap else None
            impacts.append(ic)

    actions = []
    if latest_scan:
        for a in rows("SELECT * FROM action_items WHERE case_id=? AND scan_run_id=?",
                      (cid, latest_scan["id"])):
            parse_json_fields(a, ["checklist_json"])
            # attach triggering impact's source title
            if a["impact_candidate_id"]:
                imp = next((i for i in impacts if i["id"] == a["impact_candidate_id"]), None)
                if imp and imp.get("source"):
                    a["source_title"] = imp["source"]["title"]
                    a["source_url"] = imp["source"].get("url")
            actions.append(a)

    patches = []
    for p in rows("SELECT * FROM patch_proposals WHERE case_id=?", (cid,)):
        parse_json_fields(p, ["citations_json", "evidence_refs_json", "validations_json"])
        patches.append(p)

    watches = rows("SELECT * FROM watch_entities WHERE case_id=?", (cid,))
    for w in watches:
        parse_json_fields(w, ["aliases_json"])

    profile = None
    # case_id may be NULL on older runs; resolve ownership via input_refs
    # (first ref is a claim_revision or manuscript_version id).
    for pr in conn.execute(
        "SELECT input_refs_json, parsed_output_json, model, created_at FROM model_runs "
        "WHERE stage='manuscript_understanding' AND parsed_output_json IS NOT NULL "
        "ORDER BY created_at DESC"):
        try:
            ref_ids = json.loads(pr[0]) if pr[0] else []
        except Exception:
            continue
        owner = None
        if ref_ids:
            row = conn.execute(
                "SELECT c.case_id FROM claim_revisions cr JOIN claims c ON c.id=cr.claim_id "
                "WHERE cr.id=?", (ref_ids[0],)).fetchone()
            if not row:
                row = conn.execute("SELECT case_id FROM manuscript_versions WHERE id=?",
                                   (ref_ids[0],)).fetchone()
            owner = row[0] if row else None
        if owner == cid:
            try:
                profile = {"output": json.loads(pr[1]), "model": pr[2], "created_at": pr[3]}
            except Exception:
                pass
            break

    model_runs = rows(
        "SELECT stage, provider, model, latency_ms, estimated_cost, validation_json, created_at "
        "FROM model_runs WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (cid,))
    for m in model_runs:
        parse_json_fields(m, ["validation_json"])

    audits = rows(
        "SELECT event_type, object_type, object_id, payload_json, actor_type, created_at "
        "FROM audit_events WHERE case_id=? ORDER BY created_at DESC LIMIT 30", (cid,))
    for a in audits:
        parse_json_fields(a, ["payload_json"])

    decisions = rows(
        "SELECT rd.* FROM review_decisions rd JOIN impact_candidates ic "
        "ON ic.id = rd.impact_candidate_id JOIN scan_runs sr ON sr.id = ic.scan_run_id "
        "WHERE sr.case_id=?", (cid,))
    for d in decisions:
        parse_json_fields(d, ["edited_payload_json"])

    cases_out.append({
        "id": cid, "title": case["title"], "research_question": case["research_question"],
        "is_demo": is_demo, "settings": settings.get("settings") or {},
        "created_at": case["created_at"],
        "versions": versions, "claims": claims, "scans": scans[:5],
        "latest_scan_id": latest_scan["id"] if latest_scan else None,
        "impacts": impacts, "actions": actions, "patches": patches,
        "watch_entities": watches, "profile": profile,
        "model_runs": model_runs, "audit_events": audits, "review_decisions": decisions,
    })

OUT.write_text(json.dumps({"cases": cases_out}, ensure_ascii=False, indent=1))
print("wrote", OUT, OUT.stat().st_size, "bytes")
for c in cases_out:
    print(f"- {c['title']}: claims={len(c['claims'])} impacts={len(c['impacts'])} "
          f"actions={len(c['actions'])} patches={len(c['patches'])} profile={'yes' if c['profile'] else 'no'}")
