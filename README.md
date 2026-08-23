KAORI Intelligence follow-up review patch (2026-08-23)

Changed areas
- Recommendation Summary redesigned to match Automation Control Summary and add icons per metric.
- Rule Catalog Summary redesigned to follow the same summary pattern.
- Operator Direction card background simplified to a clear surface.
- Telegram alert templates reformatted for better spacing, and action-link generation now prefers absolute URLs.
- Alert routing, Rule Catalog, and Automation Control copy shortened.
- Resolved Alert modal redesigned to align more closely with the Active Alert modal language.
- Contracts updated for the revised summary/modal/copy behavior.

Suggested commands
  git add app/templates/intelligence/partials/_recommendation_workspace_info.html \
          app/templates/intelligence/partials/_catalog_summary.html \
          app/templates/intelligence/partials/_alert_ops_routing.html \
          app/templates/intelligence/partials/_recommendation_detail_content.html \
          app/templates/intelligence/rule_catalog.html \
          app/intelligence/alert_intelligence/templates.py \
          app/intelligence/alert_intelligence/notifications.py \
          app/integrations/delivery/notification_channels/providers/telegram.py \
          app/intelligence/automation_control/overview.py \
          app/templates/intelligence/partials/_alert_ops_resolved_case_modal.html \
          tests/contracts/intelligence/test_recommendations_audit_20260815_contract.py \
          tests/contracts/intelligence/test_rule_catalog_review_20260815_contract.py \
          tests/contracts/intelligence/test_alert_management_foundation_contract.py \
          tests/contracts/intelligence/test_alert_operations_final_workspace_contract.py \
          tests/contracts/intelligence/test_intelligence_followup_copy_and_modal_contract.py \
          tests/contracts/design/test_typography_hierarchy_inventory_reference_20260823_contract.py

  git commit -m "Polish intelligence summaries, telegram alerts, and resolved modal"
