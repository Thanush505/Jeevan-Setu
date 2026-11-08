# Jeevan Setu — Complete Project Folder Structure

```text
JSF-Web_Broswer_simulator/
├── .agents/
│   └── rules/
│       └── rules.md
├── .vscode/
│   └── settings.json
├── Jeevan-Setu-Final/
│   ├── JEEVAN_SETU/
│   │   ├── chatbot/
│   │   │   ├── evaluation/
│   │   │   │   ├── __init__.py
│   │   │   │   └── evaluate_live_chatbot.py
│   │   │   ├── prompts/
│   │   │   │   ├── __init__.py
│   │   │   │   └── prompts.py
│   │   │   ├── rag/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── context_builder.py
│   │   │   │   ├── document_loader.py
│   │   │   │   ├── document_processor.py
│   │   │   │   ├── embedding_service.py
│   │   │   │   ├── rag_chatbot.py
│   │   │   │   ├── retriever.py
│   │   │   │   └── vector_store.py
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── chatbot_engine.py
│   │   │   │   ├── chatbot_service.py
│   │   │   │   └── openrouter_service.py
│   │   │   ├── tools/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── chroma_knowledge_tools.py
│   │   │   │   ├── mysql_patient_tools.py
│   │   │   │   └── tool_registry.py
│   │   │   ├── vision/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── image_loader.py
│   │   │   │   ├── image_processor.py
│   │   │   │   ├── ocr_service.py
│   │   │   │   └── vision_service.py
│   │   │   └── __init__.py
│   │   ├── data/
│   │   │   ├── sample_patients.json
│   │   │   └── test_cases.json
│   │   ├── database/
│   │   │   ├── migrations/
│   │   │   │   ├── 001_initial_schema.sql
│   │   │   │   ├── 002_core_phase2_tables.sql
│   │   │   │   ├── 003_seed_data.sql
│   │   │   │   ├── 004_auth_tokens.sql
│   │   │   │   ├── 005_remove_unused_ews_score_columns.sql
│   │   │   │   ├── 006_add_patient_name_to_decisions.sql
│   │   │   │   ├── 007_create_attendant_assistance_requests.sql
│   │   │   │   └── 008_create_simulator_scenario_transitions.sql
│   │   │   ├── cleanup_patients.py
│   │   │   ├── db.py
│   │   │   ├── init_db.py
│   │   │   ├── jeevan_setu.db
│   │   │   ├── migrate.py
│   │   │   ├── migration_manager.py
│   │   │   ├── restore_from_sqlite.py
│   │   │   ├── schema.db
│   │   │   ├── schema.sql
│   │   │   └── sync_schema.py
│   │   ├── docs/
│   │   │   └── README.md
│   │   ├── knowledge_base/
│   │   │   ├── approved_guidelines/
│   │   │   ├── clinical_protocols/
│   │   │   ├── hospital_sops/
│   │   │   └── project_documentation/
│   │   ├── logs/
│   │   │   ├── error.log
│   │   │   └── system.log
│   │   ├── models/
│   │   │   ├── alert_model.py
│   │   │   ├── assistance_request_model.py
│   │   │   ├── attendant_model.py
│   │   │   ├── audit_log_model.py
│   │   │   ├── bed_management_model.py
│   │   │   ├── bed_model.py
│   │   │   ├── chatbot_model.py
│   │   │   ├── decision_model.py
│   │   │   ├── ews_score_model.py
│   │   │   ├── explanation_model.py
│   │   │   ├── notification_model.py
│   │   │   ├── patient_model.py
│   │   │   ├── qr_token_model.py
│   │   │   ├── recommendation_model.py
│   │   │   ├── report_model.py
│   │   │   ├── role_model.py
│   │   │   ├── transfer_model.py
│   │   │   ├── user_model.py
│   │   │   ├── vitals_model.py
│   │   │   └── ward_model.py
│   │   ├── modules/
│   │   │   ├── alert_engine.py
│   │   │   ├── analytics_engine.py
│   │   │   ├── decision_engine.py
│   │   │   ├── explanation_engine.py
│   │   │   ├── report_engine.py
│   │   │   └── scoring_engine.py
│   │   ├── routes/
│   │   │   ├── alert_routes.py
│   │   │   ├── analytics_routes.py
│   │   │   ├── assistance_request_routes.py
│   │   │   ├── attendant_routes.py
│   │   │   ├── auth_api_routes.py
│   │   │   ├── auth_routes.py
│   │   │   ├── bed_routes.py
│   │   │   ├── chatbot_routes.py
│   │   │   ├── decision_routes.py
│   │   │   ├── developer_routes.py
│   │   │   ├── explanation_routes.py
│   │   │   ├── notification_routes.py
│   │   │   ├── patient_routes.py
│   │   │   ├── report_routes.py
│   │   │   ├── transfer_routes.py
│   │   │   ├── user_routes.py
│   │   │   ├── vitals_routes.py
│   │   │   └── ward_routes.py
│   │   ├── scratch/
│   │   │   ├── apply_auth_fixes.py
│   │   │   ├── check_hardcoded.py
│   │   │   ├── check_users.py
│   │   │   ├── check_vitals_data.py
│   │   │   ├── clean_db.py
│   │   │   ├── clean_extra_patients.py
│   │   │   ├── clean_extra_vitals.py
│   │   │   ├── clean_transfers.py
│   │   │   ├── cleanup_test_vital.py
│   │   │   ├── debug_api.py
│   │   │   ├── dump_schema.py
│   │   │   ├── execute_schema.py
│   │   │   ├── fill_patient_names_ews_scores.py
│   │   │   ├── generate_schema_sql.py
│   │   │   ├── get_top10.py
│   │   │   ├── inject_global_alert.py
│   │   │   ├── inspect_ews_scores.py
│   │   │   ├── inspect_seed_data.py
│   │   │   ├── list_all_patients.py
│   │   │   ├── list_logins.py
│   │   │   ├── manage_patients_count.py
│   │   │   ├── migrate_admission.py
│   │   │   ├── reduce_and_reset_patients.py
│   │   │   ├── seed_exact_10_patients.py
│   │   │   ├── seed_historical_vitals.py
│   │   │   ├── setup_standard_logins.py
│   │   │   ├── test_admin_navigation.py
│   │   │   ├── test_admission.py
│   │   │   ├── test_all_searches.py
│   │   │   ├── test_attendant_manual_login.py
│   │   │   ├── test_attendant_qr_lifecycle.py
│   │   │   ├── test_db_queries.py
│   │   │   ├── test_doctor_ews_trends.py
│   │   │   ├── test_doctor_my_patients_fixes.py
│   │   │   ├── test_live_refresh_verification.py
│   │   │   ├── test_nurse_apis.py
│   │   │   ├── test_nurse_navigation.py
│   │   │   ├── test_nurse_settings_complete.py
│   │   │   ├── test_nurse_transfer_ui_rbac.py
│   │   │   ├── test_report_sections.py
│   │   │   ├── test_transfer_recommendations_fixes.py
│   │   │   ├── test_vitals_trend_update.py
│   │   │   ├── update_admin_avatars.py
│   │   │   ├── update_frontend.py
│   │   │   ├── verify_10_patients.py
│   │   │   └── verify_api_patients.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py
│   │   │   ├── decision_service.py
│   │   │   ├── ews_service.py
│   │   │   ├── notification_service.py
│   │   │   ├── realtime_service.py
│   │   │   └── scheduler.py
│   │   ├── static/
│   │   │   ├── assets/
│   │   │   │   └── jeevan_setu_logo.png
│   │   │   ├── css/
│   │   │   │   └── style.css
│   │   │   ├── images/
│   │   │   │   ├── .gitkeep
│   │   │   │   └── jeevan_setu_logo.png
│   │   │   ├── js/
│   │   │   │   ├── alerts.js
│   │   │   │   ├── chatbot.js
│   │   │   │   ├── dashboard.js
│   │   │   │   └── global_alert_manager.js
│   │   │   ├── admin_avatar.jpg
│   │   │   ├── jeevan_setu_logo.png
│   │   │   └── nurse_avatar.jpg
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   ├── test_advanced_clinical_reasoning.py
│   │   │   ├── test_all_doctors_api.py
│   │   │   ├── test_api.py
│   │   │   ├── test_attendant_assistance_requests.py
│   │   │   ├── test_auto_refresh_system.py
│   │   │   ├── test_conversational_chatbot.py
│   │   │   ├── test_core_clinical_flow.py
│   │   │   ├── test_decision.py
│   │   │   ├── test_developer_telemetry_simulator.py
│   │   │   ├── test_direct_nurse_assistance.py
│   │   │   ├── test_doctor_approve_button_and_nurse_guardrail.py
│   │   │   ├── test_doctor_critical_alert_ews_score.py
│   │   │   ├── test_doctor_no_transfer_approved_alert.py
│   │   │   ├── test_doctor_patient_reports.py
│   │   │   ├── test_doctor_patient_summary_access.py
│   │   │   ├── test_general_chat_and_mode_isolation.py
│   │   │   ├── test_global_emergency_transfer_alerts.py
│   │   │   ├── test_mobile_responsiveness.py
│   │   │   ├── test_nurse_alerts_sidebar.py
│   │   │   ├── test_nurse_assigned_alerts.py
│   │   │   ├── test_nurse_patient_summary_ai.py
│   │   │   ├── test_nurse_transfer_dismiss_persistence.py
│   │   │   ├── test_openrouter_ai.py
│   │   │   ├── test_patient_admission_workflow.py
│   │   │   ├── test_patient_dropdown_and_rbac.py
│   │   │   ├── test_patient_pdf_report.py
│   │   │   ├── test_phase10_decision_engine.py
│   │   │   ├── test_phase11_explainable_decision.py
│   │   │   ├── test_phase12_transfer_management.py
│   │   │   ├── test_phase13_qr_attendant.py
│   │   │   ├── test_phase14_notifications_alerts.py
│   │   │   ├── test_phase15_reports.py
│   │   │   ├── test_phase16_analytics.py
│   │   │   ├── test_phase17_chatbot.py
│   │   │   ├── test_phase19_security.py
│   │   │   ├── test_phase2_database.py
│   │   │   ├── test_phase3_auth.py
│   │   │   ├── test_phase4_rbac.py
│   │   │   ├── test_phase5_user_management.py
│   │   │   ├── test_phase6_patient_management.py
│   │   │   ├── test_phase7_ward_bed_management.py
│   │   │   ├── test_phase8_vitals_management.py
│   │   │   ├── test_qr_mobile_redirection.py
│   │   │   ├── test_scenario_transitions.py
│   │   │   ├── test_scoring.py
│   │   │   ├── test_user_creation_workflow.py
│   │   │   ├── test_vector_store.py
│   │   │   ├── test_vector_store_chromadb.py
│   │   │   ├── verify_10_patients.py
│   │   │   └── verify_ews_persistence.py
│   │   ├── utils/
│   │   │   ├── auth_middleware.py
│   │   │   ├── constants.py
│   │   │   ├── decorators.py
│   │   │   ├── helpers.py
│   │   │   ├── security.py
│   │   │   └── validators.py
│   │   ├── vector_storage/
│   │   ├── .env
│   │   ├── .env.example
│   │   ├── app.py
│   │   ├── cert.pem
│   │   ├── config.py
│   │   ├── key.pem
│   │   ├── README.md
│   │   ├── requirements.txt
│   │   ├── run.md
│   │   ├── run_all_tests.py
│   │   ├── run_https_gateway.py
│   │   └── walkthrough.md
│   ├── Jeevan_setu_frontend/
│   │   ├── Admin/
│   │   │   ├── Admin_attendant_access/
│   │   │   │   ├── Admin_attendant_access.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Admin_audit_logs/
│   │   │   │   ├── Admin_audit_logs.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Admin_backup_restore/
│   │   │   │   ├── Admin_backup_restore.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Admin_beds_wards/
│   │   │   │   ├── Admin_beds_wards.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Admin_clinical_reports/
│   │   │   │   ├── Admin_clinical_reports.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Admin_ews_analytics/
│   │   │   │   ├── Admin_ews_analytics.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Admin_notification_settings/
│   │   │   │   ├── Admin_notification_settings.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Admin_patient_management/
│   │   │   │   ├── Admin_patient_management.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Admin_resource_utilization/
│   │   │   │   ├── Admin_resource_utilization.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Admin_system_settings/
│   │   │   │   ├── Admin_system_settings.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Admin_users_roles/
│   │   │   │   ├── Admin_users_roles.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Administrator_dashboard_/
│   │   │   │   ├── Administrator_dashboard_.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── admin_avatar.jpg
│   │   │   ├── admin_navigation.js
│   │   │   └── jeevan_setu_logo.png
│   │   ├── assets/
│   │   │   ├── auto_refresh_manager.js
│   │   │   └── jeevan_setu_logo.png
│   │   ├── Attendant/
│   │   │   ├── attendant_login_mobile_revised/
│   │   │   │   ├── attendant_login_mobile_revised.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── patient_update_mobile_view_replica/
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   ├── patient_update_mobile_view_replica.html
│   │   │   │   └── screen.png
│   │   │   ├── attendant_access.html
│   │   │   ├── auto_refresh_manager.js
│   │   │   ├── html5-qrcode.min.js
│   │   │   └── jeevan_setu_logo.png
│   │   ├── Developer/
│   │   │   └── Telemetry_Simulator/
│   │   │       ├── README.md
│   │   │       ├── scenarios.js
│   │   │       ├── simulator_engine.js
│   │   │       ├── Telemetry_Simulator.css
│   │   │       ├── Telemetry_Simulator.html
│   │   │       └── Telemetry_Simulator.js
│   │   ├── Doctor/
│   │   │   ├── Doctor_alerts_notifications/
│   │   │   │   ├── Doctor_alerts_notifications.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Doctor_all_patients/
│   │   │   │   ├── Doctor_all_patients.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Doctor_audit_logs/
│   │   │   │   ├── Doctor_audit_logs.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Doctor_dashboard_/
│   │   │   │   ├── Doctor_dashboard_.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Doctor_ews_calculator/
│   │   │   │   ├── Doctor_ews_calculator.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Doctor_ews_trends/
│   │   │   │   ├── Doctor_ews_trends.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Doctor_my_patients/
│   │   │   │   ├── Doctor_my_patients.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Doctor_patient_reports/
│   │   │   │   ├── Doctor_patient_reports.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Doctor_patient_search/
│   │   │   │   ├── Doctor_patient_search.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Doctor_patient_summary_ai/
│   │   │   │   ├── Doctor_patient_summary_ai.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Doctor_pending_approvals/
│   │   │   │   ├── Doctor_pending_approvals.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Doctor_settings_jeevan/
│   │   │   │   ├── Doctor_settings_jeevan.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Doctor_transfer_recommendations/
│   │   │   │   ├── Doctor_transfer_recommendations.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── Doctor_transfer_reports/
│   │   │   │   ├── Doctor_transfer_reports.html
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── screen.png
│   │   │   ├── auto_refresh_manager.js
│   │   │   ├── doctor_sidebar.js
│   │   │   ├── global_alert_manager.js
│   │   │   └── jeevan_setu_logo.png
│   │   ├── images/
│   │   │   └── jeevan_setu_logo.png
│   │   ├── Login/
│   │   │   ├── jeevan_setu_logo.png
│   │   │   ├── Login.html
│   │   │   └── screen.png
│   │   ├── Nurse/
│   │   │   ├── Nurse_alerts/
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   ├── Nurse_alerts.html
│   │   │   │   └── screen.png
│   │   │   ├── Nurse_dashboard/
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   ├── Nurse_dashboard.html
│   │   │   │   └── screen.png
│   │   │   ├── Nurse_enter_vitals/
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   ├── Nurse_enter_vitals.html
│   │   │   │   └── screen.png
│   │   │   ├── Nurse_ews_calculator/
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   ├── Nurse_ews_calculator.html
│   │   │   │   └── screen.png
│   │   │   ├── Nurse_i_o_chart/
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   ├── Nurse_i_o_chart.html
│   │   │   │   └── screen.png
│   │   │   ├── Nurse_medication_log/
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   ├── Nurse_medication_log.html
│   │   │   │   └── screen.png
│   │   │   ├── Nurse_nursing_notes/
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   ├── Nurse_nursing_notes.html
│   │   │   │   └── screen.png
│   │   │   ├── nurse_patient_monitoring/
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   ├── nurse_patient_monitoring.html
│   │   │   │   └── screen.png
│   │   │   ├── Nurse_patient_summary_ai/
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── Nurse_patient_summary_ai.html
│   │   │   ├── Nurse_reports/
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   ├── Nurse_reports.html
│   │   │   │   └── screen.png
│   │   │   ├── Nurse_settings/
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   └── Nurse_settings.html
│   │   │   ├── Nurse_tasks/
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   ├── Nurse_tasks.html
│   │   │   │   └── screen.png
│   │   │   ├── Nurse_transfers/
│   │   │   │   ├── jeevan_setu_logo.png
│   │   │   │   ├── Nurse_transfers.html
│   │   │   │   └── screen.png
│   │   │   ├── auto_refresh_manager.js
│   │   │   ├── global_alert_manager.js
│   │   │   ├── jeevan_setu_logo.png
│   │   │   ├── nurse_avatar.jpg
│   │   │   └── nurse_navigation.js
│   │   ├── auto_refresh_manager.js
│   │   ├── global_alert_manager.js
│   │   └── jeevan_setu_logo.png
│   ├── telemetry_simulator/
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   ├── test_client.py
│   │   │   ├── test_config.py
│   │   │   ├── test_scenarios.py
│   │   │   ├── test_simulator.py
│   │   │   └── test_validation.py
│   │   ├── .env.example
│   │   ├── client.py
│   │   ├── config.py
│   │   ├── logger.py
│   │   ├── models.py
│   │   ├── README.md
│   │   ├── requirements.txt
│   │   ├── scenarios.py
│   │   ├── simulator.py
│   │   └── TELEMETRY_API.md
│   ├── .env
│   ├── .env.example
│   ├── .gitignore
│   ├── Attende access.md
│   ├── CHATBOT_MERGE_REPORT.md
│   ├── check_doc_patients.py
│   ├── frontend_analysis.md
│   ├── full.md
│   ├── implementation_plan.md
│   ├── Jeevan_Setu-SRS.pdf
│   ├── MERGE_REPORT.md
│   ├── README.md
│   ├── result.md
│   ├── rules.md
│   ├── run.md
│   ├── schema.db
│   ├── Skill.md
│   └── structure.md
├── .gitignore
├── full.md
├── Jeevan_Setu_Features.pdf
├── pyrightconfig.json
├── README.md
├── rules.md
├── schema.db
└── structure.md
```
