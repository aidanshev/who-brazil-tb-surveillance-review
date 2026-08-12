from __future__ import annotations
from pathlib import Path
import importlib.util

def rebuild_who_layer(project_root: Path, who_repo: Path) -> dict:
    """Rebuild transparent WHO country report cards from an official repository checkout."""
    script=project_root/"scripts"/"build_who_actionability.py"
    spec=importlib.util.spec_from_file_location("who_builder",script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {script}")
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    output=project_root/"data"/"derived"; cards=project_root/"artifacts"/"who_report_cards"
    output.mkdir(parents=True,exist_ok=True); cards.mkdir(parents=True,exist_ok=True)
    report,summary=module.build_panel(who_repo)
    report.to_csv(output/"who_country_report_cards_2024.csv",index=False)
    report.loc[report["primary_category"]!="Routine monitoring"].to_csv(output/"who_action_queue_2024.csv",index=False)
    module.write_cards(report,cards)
    return summary


WHO_CATEGORY_PT = {
    "Diagnostic expansion / ascertainment change": "Expansão diagnóstica / mudança na detecção",
    "Incomplete latest routine reporting": "Notificação rotineira mais recente incompleta",
    "Low-volume / unstable signal": "Baixo volume / sinal instável",
    "Modeled-estimate discordance": "Discordância com estimativa modelada",
    "Persistently high burden": "Carga persistentemente elevada",
    "Possible epidemiologic increase": "Possível aumento epidemiológico",
    "Restored reporting discontinuity": "Descontinuidade de notificação restaurada",
    "Routine monitoring": "Monitoramento de rotina",
}

WHO_ACTION_PT = {
    "Continue routine monitoring; no public-data signal requires escalated review under the transparent rules.": "Manter o monitoramento de rotina; nenhum sinal nos dados públicos requer revisão intensificada segundo as regras transparentes.",
    "Maintain programme priority and monitor care-cascade indicators; this is high burden, not an emerging-hotspot designation.": "Manter a prioridade programática e monitorar os indicadores da cascata de cuidados; trata-se de carga elevada, não de designação de foco emergente.",
    "Request completion or revision of the latest routine testing and RR/MDR notification fields; suppress hotspot labeling.": "Solicitar preenchimento ou revisão dos campos mais recentes de testagem e notificação de TB-RR/MDR; não rotular como foco emergente.",
    "Review modeled-input assumptions and routine surveillance completeness; modeled estimates are secondary evidence only.": "Revisar as premissas das estimativas modeladas e a completude da vigilância rotineira; estimativas modeladas são apenas evidência secundária.",
    "Review subnational concentration, laboratory confirmation, testing mix, treatment enrollment, and transmission evidence.": "Revisar concentração subnacional, confirmação laboratorial, composição da testagem, início de tratamento e evidências de transmissão.",
    "Review testing expansion, referral changes, eligibility, and denominator shifts; interpret notification growth as improved ascertainment until corroborated.": "Revisar expansão da testagem, mudanças nos encaminhamentos, elegibilidade e denominadores; interpretar o aumento das notificações como melhora da detecção até haver corroboração.",
    "Use pooled multi-year counts or a small-area count model and avoid rate-based alarms.": "Usar contagens agrupadas de vários anos ou modelo de contagem para pequenas áreas e evitar alarmes baseados em taxas.",
    "Verify the zero/missing year, reporting backlog, platform changes, and laboratory feeds before epidemiologic interpretation.": "Verificar ano zerado/ausente, atrasos acumulados, mudanças de plataforma e fluxos laboratoriais antes da interpretação epidemiológica.",
}

WHO_EVIDENCE_PT = {
    "A for burden description; no evidence of emergence": "A para descrição da carga; sem evidência de emergência",
    "A: directly observed information limitation": "A: limitação de informação observada diretamente",
    "A: directly observed missingness": "A: ausência de dados observada diretamente",
    "B: directly visible multi-field data-quality pattern": "B: padrão de qualidade dos dados visível em múltiplos campos",
    "B: multi-indicator retrospective signal; unadjudicated": "B: sinal retrospectivo com múltiplos indicadores; não adjudicado",
    "B: testing-notification-yield pattern; unadjudicated": "B: padrão de testagem-notificação-rendimento; não adjudicado",
    "C: model-derived signal without routine corroboration": "C: sinal derivado de modelo sem corroboração rotineira",
    "Descriptive": "Descritivo",
}

def localize_who_cards(frame, language: str):
    """Add display columns without changing the source report-card data."""
    out=frame.copy()
    if language == "pt":
        out["display_category"]=out["primary_category"].map(WHO_CATEGORY_PT).fillna(out["primary_category"])
        out["display_action"]=out["recommended_action"].map(WHO_ACTION_PT).fillna(out["recommended_action"])
        out["display_evidence"]=out["evidence_grade"].map(WHO_EVIDENCE_PT).fillna(out["evidence_grade"])
    else:
        out["display_category"]=out["primary_category"]
        out["display_action"]=out["recommended_action"]
        out["display_evidence"]=out["evidence_grade"]
    return out
