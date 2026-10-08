from types import SimpleNamespace

from django.test import SimpleTestCase

from portal.services.discovery_markets import MARKET_BY_CODE, market_plan, multilingual_assignments


class Release01176DiscoveryMarketPlanningTests(SimpleTestCase):
    def settings(self, strategy='even', strength='balanced', enabled=True):
        return SimpleNamespace(
            discovery_markets=['worldwide','us','ca','de','es'],
            discovery_market_strategy=strategy,
            multilingual_exploration_enabled=enabled,
            multilingual_exploration_strength=strength,
            multilingual_languages=['German','Spanish'],
        )

    def test_even_rotation_uses_a_different_fairness_anchor_over_time(self):
        cfg=self.settings('even')
        first=[market_plan(cfg,campaign_id=4,rotation_offset=i,evidence={})['ordered_codes'][0] for i in range(5)]
        self.assertEqual(len(set(first)),5)

    def test_missing_adaptive_evidence_reports_fallback(self):
        plan=market_plan(self.settings('adaptive'),campaign_id=4,rotation_offset=0,evidence={})
        self.assertEqual(plan['requested_strategy'],'adaptive')
        self.assertEqual(plan['effective_strategy'],'even')
        self.assertIn('Adaptive',plan['fallback'])

    def test_adaptive_uses_retained_result_evidence(self):
        evidence={
            'us':{'attempts':20,'pages':20,'errors':5,'retained':0},
            'ca':{'attempts':20,'pages':30,'errors':0,'retained':2},
            'de':{'attempts':20,'pages':50,'errors':0,'retained':12},
            'es':{'attempts':20,'pages':25,'errors':1,'retained':1},
            'worldwide':{'attempts':20,'pages':20,'errors':2,'retained':1},
        }
        plan=market_plan(self.settings('adaptive'),campaign_id=4,rotation_offset=0,evidence=evidence)
        self.assertEqual(plan['effective_strategy'],'adaptive')
        self.assertEqual(plan['evidence']['de']['retained'],12)
        self.assertEqual(len(plan['ordered_codes']),5)

    def test_additional_languages_are_real_rotating_assignments(self):
        cfg=self.settings(strength='low')
        markets=[MARKET_BY_CODE[x] for x in cfg.discovery_markets]
        chosen=[multilingual_assignments(cfg,markets,rotation_offset=i)[0]['language'] for i in range(2)]
        self.assertEqual(set(chosen),{'French','German'})
        self.assertTrue(all(multilingual_assignments(cfg,markets,rotation_offset=i)[0]['source']=='market' for i in range(2)))

    def test_additional_languages_prefer_worldwide_remote(self):
        cfg=self.settings()
        cfg.multilingual_languages=['German']
        markets=[MARKET_BY_CODE['de'],MARKET_BY_CODE['worldwide']]
        assignments=multilingual_assignments(cfg,markets)
        self.assertEqual(assignments[0]['market'].code,'de')
        self.assertEqual(assignments[1]['market'].code,'worldwide')

    def test_strength_caps_assignments_and_legacy_disabled_flag_is_ignored(self):
        markets=[MARKET_BY_CODE[x] for x in self.settings().discovery_markets]
        self.assertEqual(len(multilingual_assignments(self.settings(strength='low'),markets)),2)
        self.assertEqual(len(multilingual_assignments(self.settings(strength='balanced'),markets)),3)
        self.assertEqual(len(multilingual_assignments(self.settings(strength='high'),markets)),3)
        self.assertEqual(len(multilingual_assignments(self.settings(strength='balanced',enabled=False),markets)),3)
