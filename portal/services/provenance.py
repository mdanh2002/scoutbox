"""Fit-assessment provenance helpers shared by list rendering and re-evaluation scope logic."""

CLOUD_PROVIDERS={'openai','gemini','openrouter'}


def _dict(value):
    return value if isinstance(value,dict) else {}


def fit_assessment_origin(entity):
    """Describe the effective provenance of the Fit score shown for an entity.

    The latest explicit Fit classification wins. Legacy rows are deliberately treated as
    local so they can be offered in the less-accurate/local-only re-evaluation scope.
    """
    facts=_dict(getattr(entity,'extracted_facts',None) or {})
    state=_dict(getattr(entity,'ai_state',None) or {})
    intel=_dict(getattr(entity,'company_intel',None) or {})
    origin=_dict(state.get('discovery_origin') or facts.get('discovery_origin') or intel.get('discovery_origin') or {})
    mode=str(origin.get('mode') or '').strip().lower()
    source_text=str(getattr(entity,'source','') or '')

    if not mode:
        if bool(facts.get('cloud_discovery')) or bool(intel.get('cloud_native')) or 'cloud' in source_text.casefold():
            mode='cloud'
        elif facts.get('local_pre_persistence_review') or state.get('local_lead_qualification') or 'local' in source_text.casefold():
            mode='local'

    fit={}
    for candidate in (facts.get('fit_classification'),state.get('fit_classification'),intel.get('fit_classification')):
        if isinstance(candidate,dict) and candidate:
            fit=dict(candidate); break
    fit_provider=str(fit.get('provider') or '').strip().lower()
    fit_model=str(fit.get('model') or '').strip()
    fit_source=str(fit.get('source') or '').strip()

    manual={}
    for candidate in (facts.get('manual_opportunity_filter'),state.get('manual_hidden_lead_filter'),intel.get('manual_contact_filter')):
        if isinstance(candidate,dict) and candidate:
            manual=dict(candidate); break
    manual_provider=str(manual.get('provider') or '').strip().lower()
    manual_model=str(manual.get('model') or '').strip()

    # A manual re-evaluation explicitly recalculates Fit, so its selected provider is the
    # strongest provenance signal regardless of how the record was originally discovered.
    if manual_provider:
        if manual_provider in CLOUD_PROVIDERS:
            return {
                'label':'Cloud assessment','css':'cloud','effective':'cloud',
                'title':'Fit assessed with Cloud AI'+((' · '+manual_provider)+((' · '+manual_model) if manual_model else '')),
                'provider':manual_provider,'model':manual_model,
            }
        return {
            'label':'Local AI assessment','css':'local','effective':'local',
            'title':'Fit assessed with Local AI'+((' · '+manual_provider)+((' · '+manual_model) if manual_model else ''))+' · Re-evaluate for better accuracy.',
            'provider':manual_provider,'model':manual_model,
        }

    # New pre-persistence Address Book assessments and newer discovery classifiers record
    # provider/model directly on fit_classification.
    if fit_provider:
        if fit_provider in CLOUD_PROVIDERS:
            return {
                'label':'Cloud assessment','css':'cloud','effective':'cloud',
                'title':'Fit assessed with Cloud AI'+((' · '+fit_provider)+((' · '+fit_model) if fit_model else '')),
                'provider':fit_provider,'model':fit_model,
            }
        return {
            'label':'Local AI assessment','css':'local','effective':'local',
            'title':'Fit assessed with Local AI'+((' · '+fit_provider)+((' · '+fit_model) if fit_model else ''))+' · Re-evaluate for better accuracy.',
            'provider':fit_provider,'model':fit_model,
        }

    provider=str(origin.get('provider') or facts.get('cloud_discovery_provider') or intel.get('provider') or '').strip().lower()
    model=str(origin.get('model') or facts.get('cloud_discovery_model') or intel.get('model') or '').strip()
    if mode=='cloud' or provider in CLOUD_PROVIDERS:
        return {
            'label':'Cloud entry','css':'cloud','effective':'cloud',
            'title':'Cloud-origin Fit assessment'+((' · '+provider)+((' · '+model) if model else '')),
            'provider':provider,'model':model,
        }
    if mode=='local' or provider=='ollama':
        return {
            'label':'Local AI entry','css':'local','effective':'local',
            'title':'Local-origin Fit assessment'+((' · '+provider)+((' · '+model) if model else ''))+' · Re-evaluate for better accuracy.',
            'provider':provider,'model':model,
        }
    return {
        'label':'Legacy entry (treated as local)','css':'legacy','effective':'local',
        'title':'Legacy Fit provenance · treated as Local AI · Re-evaluate for better accuracy.',
        'provider':'','model':'',
    }


def has_local_fit_assessment(entity):
    return fit_assessment_origin(entity).get('effective')=='local'


def has_cloud_fit_assessment(entity):
    return fit_assessment_origin(entity).get('effective')=='cloud'
