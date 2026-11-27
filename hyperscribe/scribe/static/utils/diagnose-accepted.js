// Re-derive `accepted` on diagnose rows that are not on the chart yet, using the same
// rule as the diagnose edit path: a coded, non-dismissed condition is accepted.
// Summaries saved under the old manual-accept rule hold coded rows with accepted=false,
// and nothing else would ever flip them.
export function deriveDiagnoseAccepted(commands) {
  return commands.map(c => {
    if (c?.command_type !== 'diagnose' || !c.data || c.already_documented || c.command_uuid) return c;
    const accepted = !!c.data.icd10_code && !c.data.rejected;
    return c.data.accepted === accepted ? c : { ...c, data: { ...c.data, accepted } };
  });
}
