from __future__ import annotations
from hashlib import sha256
from typing import Any
import numpy as np
import pandas as pd
from .schemas import AlertRecord


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator is None or not np.isfinite(denominator) or denominator <= 0:
        return np.nan
    return float(numerator / denominator)


def classify_alerts(frame: pd.DataFrame, config: dict[str, Any], release_id: str) -> pd.DataFrame:
    a = config["alerts"]
    m = config["models"]
    df = frame.sort_values(["geography_id", "period_start"]).copy()
    g = df.groupby("geography_id", group_keys=False)
    df["prior_tests"] = g["tested"].shift(1)
    df["prior_positive"] = g["rr_mdr_positive"].shift(1)
    df["prior_yield"] = g["resistance_yield"].shift(1)
    df["tests_ratio"] = [_safe_ratio(x, y) for x, y in zip(df["tested"], df["expected_tests_model"])]
    df["positive_ratio"] = [_safe_ratio(x, y) for x, y in zip(df["rr_mdr_positive"], df["expected_positive_model"])]
    df["yield_ratio"] = [_safe_ratio(x, y) for x, y in zip(df["resistance_yield"], df["expected_yield_model"])]
    country_code=str(config.get("country",{}).get("code",config.get("project",{}).get("country_code","XXX"))).upper()
    records=[]
    for row in df.itertuples():
        grade = row.data_quality_grade
        missing_current = row.notifications == 0 or not np.isfinite(row.tested)
        restored = (getattr(row, "prior_tests", np.nan) == 0) and row.tested > 0
        tier=1; signal="routine_monitoring"; reason="within_expected_range"
        rationale_en="Surveillance indicators are within the expected review range."
        rationale_pt="Os indicadores de vigilância estão dentro da faixa esperada para revisão."
        action_en="Continue routine monitoring."
        action_pt="Manter o monitoramento de rotina."
        score=float(row.positive_ratio) if np.isfinite(row.positive_ratio) else 0.0
        uncertainty=float(max(0.0, 1.0 - row.data_quality_score))
        if grade in {"C", "D"}:
            tier=0; signal="insufficient_information"; reason=row.data_quality_reasons
            rationale_en="Data quality or denominator size is insufficient for an epidemiologic interpretation."
            rationale_pt="A qualidade dos dados ou o tamanho do denominador é insuficiente para interpretação epidemiológica."
            action_en="Verify reporting, geography mapping, test coding, and completeness before interpreting trends."
            action_pt="Verificar notificação, mapeamento geográfico, codificação dos testes e completude antes de interpretar tendências."
        elif restored:
            tier=2; signal="reporting_discontinuity"; reason="zero_or_missing_then_restored"
            rationale_en="Testing or reporting resumed after a zero period; this may be a restored data flow rather than an epidemiologic increase."
            rationale_pt="A testagem ou notificação foi retomada após período zerado; pode representar restauração do fluxo de dados, não aumento epidemiológico."
            action_en="Review reporting-system continuity and backlogs."
            action_pt="Revisar continuidade do sistema de notificação e possíveis atrasos acumulados."
        elif np.isfinite(row.tests_ratio) and row.tests_ratio <= a["testing_drop_ratio"]:
            tier=2; signal="testing_capacity_drop"; reason="tests_below_expected"
            rationale_en="Testing volume is substantially below the modelled expectation."
            rationale_pt="O volume de testes está substancialmente abaixo do esperado pelo modelo."
            action_en="Check cartridge supply, instrument uptime, staffing, referral pathways, and reporting completeness."
            action_pt="Verificar cartuchos, funcionamento dos equipamentos, equipe, fluxos de referência e completude da notificação."
        elif (
            np.isfinite(row.tests_ratio) and row.tests_ratio >= a["testing_expansion_ratio"]
            and np.isfinite(row.positive_ratio) and row.positive_ratio >= a["testing_expansion_ratio"]
            and (not np.isfinite(row.yield_ratio) or row.yield_ratio <= a["yield_stable_upper_ratio"])
        ):
            tier=2; signal="diagnostic_expansion"; reason="testing_and_notifications_increased_yield_stable"
            rationale_en="More resistant cases were detected during a large testing expansion, while resistance yield remained broadly stable."
            rationale_pt="Mais casos resistentes foram detectados durante grande expansão da testagem, com rendimento de resistência aproximadamente estável."
            action_en="Interpret notification increases as possible improved ascertainment; verify eligibility and referral changes."
            action_pt="Interpretar o aumento das notificações como possível melhora da detecção; verificar elegibilidade e mudanças nos encaminhamentos."
        elif (
            bool(row.flag_operational)
            and row.expected_positive_model >= m["minimum_expected_positive_for_epidemiologic_review"]
            and np.isfinite(row.yield_ratio) and row.yield_ratio >= a["yield_increase_ratio"]
            and np.isfinite(row.tests_ratio) and a["stable_testing_lower_ratio"] <= row.tests_ratio <= a["stable_testing_upper_ratio"]
        ):
            tier=4 if (bool(row.flag_ai) and row.conventional_detector_agreement >= a["required_detector_agreement_for_tier4"]) else 3
            signal="corroborated_priority_signal" if tier == 4 else "epidemiologic_review_signal"
            reason="positive_and_yield_above_expected_without_testing_expansion"
            rationale_en="RR/MDR-positive results and resistance yield exceeded expectation without a proportional testing increase."
            rationale_pt="Os resultados positivos RR/MDR e o rendimento de resistência superaram o esperado sem aumento proporcional da testagem."
            action_en="Conduct structured epidemiologic and laboratory review; do not declare an outbreak without corroboration."
            action_pt="Realizar revisão epidemiológica e laboratorial estruturada; não declarar surto sem corroboração."
        uid_source=f"{release_id}|{country_code}|{row.geography_id}|{row.period}|{signal}"
        record=AlertRecord(
            alert_uid=sha256(uid_source.encode()).hexdigest()[:24], release_id=release_id,
            country_code=country_code, region_id=str(row.geography_id), region_name=str(row.geography_name), period=str(row.period),
            tier=tier, signal_type=signal, reason_code=reason, data_quality_grade=grade,
            observed_tests=float(row.tested), expected_tests=float(row.expected_tests_model) if np.isfinite(row.expected_tests_model) else 0.0,
            observed_positive=float(row.rr_mdr_positive), expected_positive=float(row.expected_positive_model) if np.isfinite(row.expected_positive_model) else 0.0,
            observed_yield=float(row.resistance_yield) if np.isfinite(row.resistance_yield) else 0.0,
            expected_yield=float(row.expected_yield_model) if np.isfinite(row.expected_yield_model) else 0.0,
            score=score, uncertainty=uncertainty,
            rationale_en=rationale_en, rationale_pt=rationale_pt,
            recommended_action_en=action_en, recommended_action_pt=action_pt,
        )
        records.append(record.to_dict())
    return pd.DataFrame(records).sort_values(["tier", "score"], ascending=[False, False]).reset_index(drop=True)
