-- ДОКУМЕНТ: db/05_final_state_check_ext01.sql — СОБРАН db/build_final_ext.mjs, руками не править
-- ИСТОЧНИК H1.31 05: sha256 1e584d2e412103efa5d1acb0c00c761dd82ca086bbd060571dff666146578ea1
-- РАСШИРЕНИЕ 02: sha256 02619df434209f8c53b6d916209d866996e69274939a1e19b60de0f03158634e
-- НАЗНАЧЕНИЕ: терминальная проверка H1.31 05 с точным списком отличий Z-EXT-01 (см. сборщик).
\set ON_ERROR_STOP on

-- 05_final_state_check.sql — терминальная административная проверка.
-- Запускает АДМИНИСТРАТОР КЛАСТЕРА, последним файлом пакета: после
-- закрытия окна мигратора и после файла 04. Обёртка раздела 25.7
-- объявляет успех только тогда, когда этот файл прошёл целиком.
--
-- Файл ничего не меняет. Ни одной команды выдачи права, отзыва права,
-- смены признаков роли или смены действующей роли в нём нет: он читает
-- каталоги и возбуждает отказ. Починка в конце прогона скрыла бы
-- причину расхождения, а нужна как раз причина.
--
-- Проверка, стоящая не последней, не проверяет ничего: команду всегда
-- можно дописать после неё. Самопроверка файла 01 знает только то, что
-- видно внутри файла 01 и до его фиксации; она не видит файла 00, не
-- видит файла 04 и не видит состояния ролей кластера. Поэтому пакет
-- заканчивается этим файлом (замечание M-H113-R13-01).
--
-- Значений паролей файл не читает и не печатает. Сравнивается только
-- признак «задан» или «не задан»: отпечаток пароля — такой же секрет,
-- как сам пароль.
DECLARE bem_final_guard CURSOR FOR SELECT 1;
CLOSE bem_final_guard;

-- H1.26, D1 (пробы R46, п. 16): ограничения целиком, в обе стороны.
-- Повторный прогон файла 01 возвращает снятое ограничение, но только
-- известное ему. Здесь сверяется точное множество видов p, u, f и c в
-- трёх схемах: не хватает — отказ; лишнее или с другой печатной
-- формой — тоже отказ. Схема и имя берутся из pg_namespace, pg_class и
-- pg_type, печатная форма — при пути поиска pg_catalog. Ограничение-
-- триггер (вид t) сверяет пункт 7 следующего блока.
DO $$
-- ПОКРЫТИЕ: K-R46-01
DECLARE
    v_constraints constant text[] := ARRAY[
        'TABLE|bem_control.authority_guard|authority_guard_pkey|PRIMARY KEY (scope)',
        'TABLE|bem_control.backup_window|backup_window_pkey|PRIMARY KEY (id)',
        'TABLE|bem_core.actor|actor_pkey|PRIMARY KEY (actor_id)',
        'TABLE|bem_core.actor_authority|actor_authority_pkey|PRIMARY KEY (id)',
        'TABLE|bem_core.actor_delegation|actor_delegation_pkey|PRIMARY KEY (id)',
        'TABLE|bem_core.audit_assignment|audit_assignment_pkey|PRIMARY KEY (id)',
        'TABLE|bem_core.audit_record|audit_record_pkey|PRIMARY KEY (id)',
        'TABLE|bem_core.command_log|command_log_pkey|PRIMARY KEY (command_id)',
        'TABLE|bem_core.evidence|evidence_pkey|PRIMARY KEY (id)',
        'TABLE|bem_core.handoff_packet|handoff_packet_pkey|PRIMARY KEY (id)',
        'TABLE|bem_core.outbox|outbox_pkey|PRIMARY KEY (id)',
        'TABLE|bem_control.outbox_kind_policy|outbox_kind_policy_pkey|PRIMARY KEY (kind, version)',
        'TABLE|bem_control.outbox_kind_policy|outbox_kind_policy_kind_check|CHECK ((kind ~ ''^[A-Za-z][A-Za-z0-9_.:-]{0,127}$''::text))',
        'TABLE|bem_control.outbox_kind_policy|outbox_kind_policy_version_check|CHECK ((version >= 1))',
        'TABLE|bem_control.outbox_kind_policy|outbox_kind_policy_adapter_version_check|CHECK ((btrim(adapter_version) <> ''''::text))',
        'TABLE|bem_control.outbox_kind_policy|outbox_kind_policy_key_scheme_check|CHECK ((btrim(key_scheme) <> ''''::text))',
        'TABLE|bem_control.outbox_kind_policy|outbox_kind_policy_evidence_check|CHECK ((btrim(evidence) <> ''''::text))',
        'TABLE|bem_control.outbox_send_fence|outbox_send_fence_pkey|PRIMARY KEY (outbox_id, lease_epoch)',
        'TABLE|bem_control.outbox_send_fence|outbox_send_fence_worker_check|CHECK ((btrim(worker) <> ''''::text))',
        'TABLE|bem_control.outbox_send_fence|outbox_send_fence_runtime_instance_check|CHECK ((btrim(runtime_instance) <> ''''::text))',
        'TABLE|bem_control.outbox_send_fence|outbox_send_fence_method_check|CHECK ((method = ANY (ARRAY[''PROCESS_TERMINATED''::text, ''CONTAINER_TERMINATED''::text])))',
        'TABLE|bem_core.schema_migration|schema_migration_pkey|PRIMARY KEY (version)',
        'TABLE|bem_core.subject|subject_pkey|PRIMARY KEY (id)',
        'TABLE|bem_core.subject_author|subject_author_pkey|PRIMARY KEY (subject_id, actor_id)',
        'TABLE|bem_core.tenant|tenant_pkey|PRIMARY KEY (id)',
        'TABLE|bem_core.usage_record|usage_record_pkey|PRIMARY KEY (id)',
        'TABLE|bem_core.user_tenant_membership|user_tenant_membership_pkey|PRIMARY KEY (id)',
        'TABLE|bem_core.work_item|work_item_pkey|PRIMARY KEY (id)',
        'TABLE|bem_core.actor|actor_db_role_uniq|UNIQUE (db_role)',
        'TABLE|bem_core.actor|actor_unique_pair|UNIQUE (actor_id, provider)',
        'TABLE|bem_core.audit_assignment|audit_assignment_uniq|UNIQUE (subject_id, auditor_actor)',
        'TABLE|bem_core.audit_record|audit_one_per_head_auditor|UNIQUE (subject_id, head_sha, auditor_actor)',
        'TABLE|bem_core.evidence|evidence_tenant_id_uniq|UNIQUE (tenant_id, id)',
        'TABLE|bem_core.handoff_packet|handoff_packet_no_uniq|UNIQUE (work_item_id, handoff_no)',
        'TABLE|bem_core.outbox|outbox_command_uniq|UNIQUE (command_id)',
        'TABLE|bem_core.outbox|outbox_idem_uniq|UNIQUE (tenant_id, kind, idempotency_key)',
        'TABLE|bem_core.subject|subject_tenant_id_uniq|UNIQUE (tenant_id, id)',
        'TABLE|bem_core.work_item|work_item_process_instance_uniq|UNIQUE (process_instance_id)',
        'TABLE|bem_core.work_item|work_item_tenant_id_uniq|UNIQUE (tenant_id, id)',
        'TABLE|bem_core.actor_authority|actor_authority_actor_id_fkey|FOREIGN KEY (actor_id) REFERENCES bem_core.actor(actor_id)',
        'TABLE|bem_core.actor_authority|actor_authority_tenant_id_fkey|FOREIGN KEY (tenant_id) REFERENCES bem_core.tenant(id)',
        'TABLE|bem_core.actor_delegation|actor_delegation_actor_id_fkey|FOREIGN KEY (actor_id) REFERENCES bem_core.actor(actor_id)',
        'TABLE|bem_core.actor_delegation|actor_delegation_granted_by_fkey|FOREIGN KEY (granted_by) REFERENCES bem_core.actor(actor_id)',
        'TABLE|bem_core.actor_delegation|actor_delegation_revoked_by_fkey|FOREIGN KEY (revoked_by) REFERENCES bem_core.actor(actor_id)',
        'TABLE|bem_core.audit_assignment|audit_assignment_actor_fk|FOREIGN KEY (auditor_actor, auditor_provider) REFERENCES bem_core.actor(actor_id, provider)',
        'TABLE|bem_core.audit_assignment|audit_assignment_subject_fk|FOREIGN KEY (tenant_id, subject_id) REFERENCES bem_core.subject(tenant_id, id)',
        'TABLE|bem_core.audit_record|audit_actor_fk|FOREIGN KEY (auditor_actor, auditor_provider) REFERENCES bem_core.actor(actor_id, provider)',
        'TABLE|bem_core.audit_record|audit_evidence_fk|FOREIGN KEY (tenant_id, evidence_id) REFERENCES bem_core.evidence(tenant_id, id)',
        'TABLE|bem_core.audit_record|audit_subject_fk|FOREIGN KEY (tenant_id, subject_id) REFERENCES bem_core.subject(tenant_id, id)',
        'TABLE|bem_core.command_log|command_log_work_item_fk|FOREIGN KEY (tenant_id, work_item_id) REFERENCES bem_core.work_item(tenant_id, id)',
        'TABLE|bem_core.evidence|evidence_actor_fk|FOREIGN KEY (actor_id) REFERENCES bem_core.actor(actor_id)',
        'TABLE|bem_core.evidence|evidence_delegation_fk|FOREIGN KEY (delegation_id) REFERENCES bem_core.actor_delegation(id)',
        'TABLE|bem_core.evidence|evidence_tenant_id_fkey|FOREIGN KEY (tenant_id) REFERENCES bem_core.tenant(id)',
        'TABLE|bem_core.handoff_packet|handoff_packet_accepted_by_fkey|FOREIGN KEY (accepted_by) REFERENCES bem_core.actor(actor_id)',
        'TABLE|bem_core.handoff_packet|handoff_packet_work_item_fk|FOREIGN KEY (tenant_id, work_item_id) REFERENCES bem_core.work_item(tenant_id, id)',
        'TABLE|bem_core.outbox|outbox_work_item_fk|FOREIGN KEY (tenant_id, work_item_id) REFERENCES bem_core.work_item(tenant_id, id)',
        'TABLE|bem_core.subject|subject_tenant_id_fkey|FOREIGN KEY (tenant_id) REFERENCES bem_core.tenant(id)',
        'TABLE|bem_core.subject|subject_work_item_fk|FOREIGN KEY (tenant_id, work_item_id) REFERENCES bem_core.work_item(tenant_id, id)',
        'TABLE|bem_core.subject_author|subject_author_actor_fk|FOREIGN KEY (actor_id, provider) REFERENCES bem_core.actor(actor_id, provider)',
        'TABLE|bem_core.subject_author|subject_author_subject_fk|FOREIGN KEY (tenant_id, subject_id) REFERENCES bem_core.subject(tenant_id, id)',
        'TABLE|bem_core.usage_record|usage_record_work_item_fk|FOREIGN KEY (tenant_id, work_item_id) REFERENCES bem_core.work_item(tenant_id, id)',
        'TABLE|bem_core.user_tenant_membership|user_tenant_membership_tenant_id_fkey|FOREIGN KEY (tenant_id) REFERENCES bem_core.tenant(id)',
        'TABLE|bem_core.work_item|work_item_tenant_id_fkey|FOREIGN KEY (tenant_id) REFERENCES bem_core.tenant(id)',
        'TABLE|bem_control.backup_window|backup_window_id_check|CHECK ((id = 1))',
        'TABLE|bem_core.actor|actor_provider_prefix|CHECK ((((provider = ''anthropic''::bem_core.provider) AND ((actor_id)::text ~~ ''claude:%''::text)) OR ((provider = ''openai''::bem_core.provider) AND ((actor_id)::text ~~ ''codex:%''::text)) OR ((provider = ''human''::bem_core.provider) AND ((actor_id)::text ~~ ''human:%''::text))))',
        'TABLE|bem_core.actor_authority|actor_authority_authority_check|CHECK ((authority = ANY (ARRAY[''OPERATOR''::text, ''AUDIT_COORDINATOR''::text, ''TENANT_PROVISIONER''::text])))',
        'TABLE|bem_core.actor_delegation|actor_delegation_reason_check|CHECK (((length(btrim(reason)) >= 3) AND (length(btrim(reason)) <= 500)))',
        'TABLE|bem_core.actor_delegation|actor_delegation_revocation_pair|CHECK ((((revoked_at IS NULL) AND (revoked_by IS NULL)) OR ((revoked_at IS NOT NULL) AND (revoked_by IS NOT NULL))))',
        'DOMAIN|bem_core.actor_id|actor_id_check|CHECK ((VALUE ~ ''^(claude|codex|human):[a-z0-9_.-]{1,64}$''::text))',
        'TABLE|bem_core.command_log|command_log_fingerprint_version_check|CHECK ((fingerprint_version = ANY (ARRAY[1, 2])))',
        'TABLE|bem_core.command_log|command_log_kind_agrees|CHECK (((has_outbox AND (kind IS NOT NULL)) OR ((NOT has_outbox) AND (kind IS NULL) AND (outbox_id IS NULL))))',
        'TABLE|bem_core.evidence|evidence_delegation_basis|CHECK (((identity_contract = 1) OR ((identity_mode = ''BOUND''::text) AND (delegation_id IS NULL)) OR ((identity_mode = ''DELEGATED''::text) AND (delegation_id IS NOT NULL))))',
        'TABLE|bem_core.evidence|evidence_identity_contract_check|CHECK ((identity_contract = ANY (ARRAY[1, 2])))',
        'TABLE|bem_core.evidence|evidence_identity_mode_check|CHECK ((identity_mode = ANY (ARRAY[''BOUND''::text, ''DELEGATED''::text])))',
        'TABLE|bem_core.handoff_packet|handoff_packet_accepted_pair|CHECK ((((accepted_at IS NULL) AND (accepted_by IS NULL)) OR ((accepted_at IS NOT NULL) AND (accepted_by IS NOT NULL))))',
        'TABLE|bem_core.outbox|outbox_idempotency_key_check|CHECK ((idempotency_key ~ ''^[0-9a-f]{64}$''::text))',
        'TABLE|bem_core.outbox|outbox_reconciled_outcome_check|CHECK ((reconciled_outcome = ANY (ARRAY[''CONFIRMED_SENT''::text, ''CONFIRMED_NOT_SENT''::text, ''UNRESOLVED''::text])))',
        'TABLE|bem_core.outbox|outbox_status_check|CHECK ((status = ANY (ARRAY[''PENDING''::text, ''LEASED''::text, ''SENT''::text, ''FAILED''::text, ''UNKNOWN_OUTCOME''::text, ''DEAD_LETTER''::text])))',
        'TABLE|bem_core.subject|subject_criticality_check|CHECK ((criticality = ANY (ARRAY[''CRITICAL''::text, ''NORMAL''::text])))',
        'TABLE|bem_core.subject|subject_scope_check|CHECK ((scope = ANY (ARRAY[''WORKING''::text, ''BEM954_PROTOCOL''::text, ''ZAVOD_PRODUCT_RELEASE''::text])))',
        'TABLE|bem_core.usage_record|usage_record_measured_by_check|CHECK ((measured_by = ANY (ARRAY[''PROVIDER_REPORTED''::text, ''LOCAL_ESTIMATE''::text])))',
        'TABLE|bem_core.usage_record|usage_record_outcome_check|CHECK ((outcome = ANY (ARRAY[''OK''::text, ''PROVIDER_ERROR''::text, ''SOFT_LIMIT''::text, ''HANDOFF''::text])))',
        'TABLE|bem_core.user_tenant_membership|user_tenant_membership_role_check|CHECK ((role = ANY (ARRAY[''tenant_admin''::text, ''member''::text, ''viewer''::text])))',
        'TABLE|bem_core.work_item|work_item_criticality_check|CHECK ((criticality = ANY (ARRAY[''CRITICAL''::text, ''NORMAL''::text])))'];
    v_path  text;
    v_miss  text;
    v_extra text;
BEGIN
    v_path := current_setting('search_path');
    PERFORM set_config('search_path', 'pg_catalog', true);
    WITH live AS (
        SELECT CASE WHEN c.conrelid <> 0
                    THEN 'TABLE|' || rn.nspname || '.' || rc.relname
                    ELSE 'DOMAIN|' || tn.nspname || '.' || ty.typname END
               || '|' || c.conname || '|' || pg_get_constraintdef(c.oid) AS fp
          FROM pg_constraint c
          JOIN pg_namespace n ON n.oid = c.connamespace
          LEFT JOIN pg_class rc ON rc.oid = c.conrelid
          LEFT JOIN pg_namespace rn ON rn.oid = rc.relnamespace
          LEFT JOIN pg_type ty ON ty.oid = c.contypid
          LEFT JOIN pg_namespace tn ON tn.oid = ty.typnamespace
         WHERE n.nspname IN ('bem_core', 'bem_engine', 'bem_control')
           AND c.contype IN ('p', 'u', 'f', 'c'))
    SELECT (SELECT string_agg(x, '; ' ORDER BY x COLLATE "C")
              FROM unnest(v_constraints) AS x
             WHERE x NOT IN (SELECT fp FROM live)),
           (SELECT string_agg(fp, '; ' ORDER BY fp COLLATE "C")
              FROM live
             WHERE fp <> ALL (v_constraints))
      INTO v_miss, v_extra;
    PERFORM set_config('search_path', v_path, true);
    IF v_miss IS NOT NULL THEN
        RAISE EXCEPTION 'FINAL_CONSTRAINT_MISMATCH: объявленных ограничений нет: %', v_miss;
    END IF;
    IF v_extra IS NOT NULL THEN
        RAISE EXCEPTION 'FINAL_CONSTRAINT_MISMATCH: ограничений сверх договора: %', v_extra;
    END IF;
END
$$;

DO $$
-- ПОКРЫТИЕ: K-R15-12, K-R15-13, K-R15-14
DECLARE
    v_roles   constant text[] := ARRAY[
        'backup_reader|no|no|no|no|no|yes|yes|0',
        'bem_backup_admin|yes|no|no|no|no|no|no|-1',
        'bem_backup_ctl_owner|no|no|no|yes|no|no|yes|-1',
        'bem_bootstrap_admin|yes|no|no|no|no|no|yes|0',
        'bem_control_owner|no|no|no|no|no|yes|yes|-1',
        'bem_core_owner|no|no|no|no|no|no|yes|-1',
        'bem_engine_owner|no|no|no|no|no|no|yes|-1',
        'bem_engine_rw|yes|no|no|no|no|no|yes|-1',
        'bem_governance|no|no|no|no|no|no|yes|-1',
        'bem_kernel_rw|yes|no|no|no|no|no|yes|-1',
        'schema_migrator|no|no|no|no|no|no|yes|-1'];
    v_members constant text[] := ARRAY[
        'backup_reader|bem_backup_ctl_owner|BOOTSTRAP_SUPERUSER|yes|no|no',
        'bem_governance|bem_bootstrap_admin|BOOTSTRAP_SUPERUSER|no|yes|yes',
        'pg_signal_backend|bem_backup_ctl_owner|BOOTSTRAP_SUPERUSER|no|yes|yes'];
    v_secrets constant text[] := ARRAY[
        'backup_reader|password:null|valid_until:none|config:none',
        'bem_backup_admin|password:null|valid_until:none|config:none',
        'bem_backup_ctl_owner|password:none|valid_until:none|config:none',
        'bem_bootstrap_admin|password:null|valid_until:none|config:none',
        'bem_control_owner|password:none|valid_until:none|config:none',
        'bem_core_owner|password:none|valid_until:none|config:none',
        'bem_engine_owner|password:none|valid_until:none|config:none',
        'bem_engine_rw|password:none|valid_until:none|config:none',
        'bem_governance|password:none|valid_until:none|config:none',
        'bem_kernel_rw|password:none|valid_until:none|config:none',
        'schema_migrator|password:none|valid_until:none|config:none'];
    v_login   constant text[] := ARRAY[
        'bem_backup_admin',
        'bem_bootstrap_admin',
        'bem_engine_rw',
        'bem_kernel_rw'];
    v_rls     constant text[] := ARRAY[
        'bem_core.audit_assignment',
        'bem_core.audit_record',
        'bem_core.command_log',
        'bem_core.evidence',
        'bem_core.handoff_packet',
        'bem_core.outbox',
        'bem_core.subject',
        'bem_core.subject_author',
        'bem_core.usage_record',
        'bem_core.user_tenant_membership',
        'bem_core.work_item'];
    -- Политика целиком: схема с таблицей, имя, команда, режим,
    -- получатели и оба выражения. Прежний список держал четыре поля,
    -- и политика с прежним именем, но выражением «всё видно» проходила
    -- насквозь (замечание M-H114-R14-01, подделка I-H114-02).
    -- Выражения нормализованы: приставка схемы снята, как и в
    -- самопроверке файла 01.
    v_policy  constant text[] := ARRAY[
        'bem_core.audit_assignment|tenant_isolation|ALL|PERMISSIVE|public|(tenant_id = current_tenant())|(tenant_id = current_tenant())',
        'bem_core.audit_record|tenant_isolation|ALL|PERMISSIVE|public|(tenant_id = current_tenant())|(tenant_id = current_tenant())',
        'bem_core.command_log|tenant_isolation|ALL|PERMISSIVE|public|(tenant_id = current_tenant())|(tenant_id = current_tenant())',
        'bem_core.evidence|tenant_isolation|ALL|PERMISSIVE|public|(tenant_id = current_tenant())|(tenant_id = current_tenant())',
        'bem_core.handoff_packet|tenant_isolation|ALL|PERMISSIVE|public|(tenant_id = current_tenant())|(tenant_id = current_tenant())',
        'bem_core.outbox|tenant_isolation|ALL|PERMISSIVE|public|(tenant_id = current_tenant())|(tenant_id = current_tenant())',
        'bem_core.subject|tenant_isolation|ALL|PERMISSIVE|public|(tenant_id = current_tenant())|(tenant_id = current_tenant())',
        'bem_core.subject_author|tenant_isolation|ALL|PERMISSIVE|public|(tenant_id = current_tenant())|(tenant_id = current_tenant())',
        'bem_core.usage_record|tenant_isolation|ALL|PERMISSIVE|public|(tenant_id = current_tenant())|(tenant_id = current_tenant())',
        'bem_core.user_tenant_membership|tenant_isolation|ALL|PERMISSIVE|public|(tenant_id = current_tenant())|(tenant_id = current_tenant())',
        'bem_core.work_item|tenant_isolation|ALL|PERMISSIVE|public|(tenant_id = current_tenant())|(tenant_id = current_tenant())'];
    v_trigger constant text[] := ARRAY[
        'bem_core.audit_record|audit_record_append_only|27||bem_core.forbid_update_delete()|O|f|f|f|f|0',
        'bem_core.audit_record|audit_record_head_match|7||bem_core.audit_head_matches_subject()|O|f|f|f|f|0',
        'bem_core.audit_record|audit_record_no_self_audit|7||bem_core.forbid_self_audit()|O|f|f|f|f|0',
        'bem_core.command_log|command_log_append_only|11||bem_core.forbid_update_delete()|O|f|f|f|f|0',
        'bem_core.evidence|evidence_append_only|27||bem_core.forbid_update_delete()|O|f|f|f|f|0',
        'bem_core.evidence|evidence_identity|7||bem_core.evidence_identity()|O|f|f|f|f|0',
        'bem_core.subject_author|subject_author_append_only|27||bem_core.forbid_update_delete()|O|f|f|f|f|0',
        'bem_core.subject_author|subject_author_frozen|7||bem_core.forbid_author_change_after_publish()|O|f|f|f|f|0',
        'bem_core.subject|subject_requires_author|21|published_at|bem_core.require_at_least_one_author()|O|t|t|t|t|0'];
    -- Мостовой триггер пакета передачи. Он существует только пока
    -- столбец суммы необязателен: файл 02 создаёт его для старых строк
    -- и удаляет сразу, как только столбец становится обязательным, а
    -- чистая установка файлом 01 не создаёт его никогда. Поэтому он
    -- ожидается условно, а не всегда.
    v_trigger_legacy constant text[] := ARRAY[
        'bem_core.handoff_packet|handoff_requires_sha|7||bem_core.handoff_requires_sha()|O|f|f|f|f|0'];
    -- Определения тех же триггеров целиком (R31, замечание
    -- C-H115-R15-01): схема.таблица | имя | условие WHEN | байты
    -- аргументов | строка pg_get_triggerdef(oid, true) при пути поиска
    -- pg_catalog, с пробелами, сжатыми до одного. Списки печатает
    -- сверщик раздела 15.11 и сверяет их с каноном в обе стороны.
    v_trigger_def constant text[] := ARRAY[
        'bem_core.audit_record|audit_record_append_only|||CREATE TRIGGER audit_record_append_only BEFORE DELETE OR UPDATE ON bem_core.audit_record FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_update_delete()',
        'bem_core.audit_record|audit_record_head_match|||CREATE TRIGGER audit_record_head_match BEFORE INSERT ON bem_core.audit_record FOR EACH ROW EXECUTE FUNCTION bem_core.audit_head_matches_subject()',
        'bem_core.audit_record|audit_record_no_self_audit|||CREATE TRIGGER audit_record_no_self_audit BEFORE INSERT ON bem_core.audit_record FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_self_audit()',
        'bem_core.command_log|command_log_append_only|||CREATE TRIGGER command_log_append_only BEFORE DELETE ON bem_core.command_log FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_update_delete()',
        'bem_core.evidence|evidence_append_only|||CREATE TRIGGER evidence_append_only BEFORE DELETE OR UPDATE ON bem_core.evidence FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_update_delete()',
        'bem_core.evidence|evidence_identity|||CREATE TRIGGER evidence_identity BEFORE INSERT ON bem_core.evidence FOR EACH ROW EXECUTE FUNCTION bem_core.evidence_identity()',
        'bem_core.subject_author|subject_author_append_only|||CREATE TRIGGER subject_author_append_only BEFORE DELETE OR UPDATE ON bem_core.subject_author FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_update_delete()',
        'bem_core.subject_author|subject_author_frozen|||CREATE TRIGGER subject_author_frozen BEFORE INSERT ON bem_core.subject_author FOR EACH ROW EXECUTE FUNCTION bem_core.forbid_author_change_after_publish()',
        'bem_core.subject|subject_requires_author|new.published_at IS NOT NULL||CREATE CONSTRAINT TRIGGER subject_requires_author AFTER INSERT OR UPDATE OF published_at ON bem_core.subject DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN (new.published_at IS NOT NULL) EXECUTE FUNCTION bem_core.require_at_least_one_author()'];
    v_trigger_def_legacy constant text[] := ARRAY[
        'bem_core.handoff_packet|handoff_requires_sha|||CREATE TRIGGER handoff_requires_sha BEFORE INSERT ON bem_core.handoff_packet FOR EACH ROW EXECUTE FUNCTION bem_core.handoff_requires_sha()'];
    -- Договор функции: подпись, владелец, режим исполнения и весь
    -- proconfig целиком, а не только путь поиска. Настройка сверх
    -- договора — тоже расхождение: она может, например, поменять
    -- часовой пояс или правила сравнения строк внутри тела
    -- (замечание M-H114-R14-01). Значение `none` означает, что
    -- настроек у функции нет вовсе.
    v_func    constant text[] := ARRAY[
        'bem_control.accept_handoff(uuid, uuid, integer, text)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_catalog, pg_temp',
        'bem_control.apply_transition(uuid, uuid, integer, text[], text, uuid, text, jsonb, jsonb)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_catalog, pg_temp',
        'bem_control.assert_authority(text, uuid)|bem_control_owner|invoker|search_path=bem_core, pg_catalog, pg_temp',
        'bem_control.assert_command_identity(bem_core.command_log, uuid, uuid, uuid, text, text, boolean, text)|bem_control_owner|invoker|search_path=pg_catalog, pg_temp',
        'bem_control.assert_tenant(uuid)|bem_control_owner|invoker|search_path=bem_core, pg_catalog, pg_temp',
        'bem_control.assign_auditor(uuid, uuid, text, jsonb)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_catalog, pg_temp',
        'bem_control.authority_barrier(text)|bem_control_owner|invoker|search_path=bem_control, pg_catalog, pg_temp',
        'bem_control.backup_window_assert_closed()|bem_backup_ctl_owner|definer|search_path=pg_catalog, pg_temp',
        'bem_control.backup_window_drain()|bem_backup_ctl_owner|definer|search_path=pg_catalog, pg_temp',
        'bem_control.backup_window_lock()|bem_backup_ctl_owner|definer|search_path=pg_catalog, pg_temp',
        'bem_control.backup_window_open(integer)|bem_backup_ctl_owner|definer|search_path=pg_catalog, pg_temp',
        'bem_control.bind_process_instance(uuid, uuid, text)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_catalog, pg_temp',
        'bem_control.claim_outbox_batch(integer, interval, text)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_temp',
        'bem_control.command_fingerprint(uuid, uuid, text, integer, text[], text, text, jsonb, jsonb)|bem_control_owner|invoker|search_path=pg_catalog, pg_temp',
        'bem_control.create_actor(text, bem_core.provider, uuid, name)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_catalog, pg_temp',
        'bem_control.create_tenant(uuid, text, text, uuid, jsonb)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_catalog, pg_temp',
        'bem_control.create_work_item(uuid, uuid, text, text, jsonb)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_catalog, pg_temp',
        'bem_control.current_actor_checked(uuid)|bem_control_owner|invoker|search_path=bem_core, pg_catalog, pg_temp',
        'bem_control.data_digest(regclass)|bem_control_owner|definer|DateStyle=ISO, YMD;TimeZone=UTC;bytea_output=hex;extra_float_digits=3;search_path=bem_control, bem_core, pg_catalog, pg_temp',
        'bem_control.database_digest()|bem_control_owner|definer|search_path=bem_control, pg_catalog, pg_temp',
        'bem_control.dead_letter_outbox_row(uuid, uuid, text)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_catalog, pg_temp',
        'bem_control.evidence_write(uuid, text, jsonb)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_temp',
        'bem_control.finish_outbox_row(uuid, bigint, text, text, jsonb)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_temp',
        'bem_control.grant_authority(text, text, uuid)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_catalog, pg_temp',
        'bem_control.grant_delegation(name, text, text)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_catalog, pg_temp',
        'bem_control.lock_subject(uuid, uuid)|bem_control_owner|invoker|search_path=bem_core, pg_catalog, pg_temp',
        'bem_control.operator_lock_key()|bem_control_owner|invoker|search_path=pg_catalog, pg_temp',
        'bem_control.outbox_retry_limit()|bem_control_owner|invoker|search_path=pg_catalog, pg_temp',
        'bem_control.publish_subject(uuid, uuid, uuid, text, text, text, text[], jsonb)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_catalog, pg_temp',
        'bem_control.reconcile_unknown_outcome(uuid, uuid, text, jsonb)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_catalog, pg_temp',
        'bem_control.record_audit_verdict(uuid, uuid, text, text, jsonb)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_catalog, pg_temp',
        'bem_control.record_backup_evidence(jsonb)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_catalog, pg_temp',
        'bem_control.record_evidence(uuid, text, jsonb)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_temp',
        'bem_control.record_handoff(uuid, uuid, integer, jsonb, text)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_catalog, pg_temp',
        'bem_control.record_usage(uuid, uuid, integer, text, text, integer, integer, integer, integer, integer, integer, text, text)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_catalog, pg_temp',
        'bem_control.release_subject(uuid, uuid, text)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_catalog, pg_temp',
        'bem_control.revoke_auditor(uuid, uuid, text, jsonb)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_catalog, pg_temp',
        'bem_control.revoke_authority(text, text, uuid)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_catalog, pg_temp',
        'bem_control.revoke_delegation(uuid)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_catalog, pg_temp',
        'bem_control.schema_digest(regclass)|bem_control_owner|definer|search_path=pg_catalog, pg_temp',
        'bem_control.service_tenant()|bem_control_owner|invoker|search_path=pg_catalog, pg_temp',
        'bem_control.set_tenant_membership(uuid, uuid, text, boolean)|bem_control_owner|definer|search_path=bem_control, bem_core, pg_temp',
        'bem_core.audit_head_matches_subject()|bem_core_owner|invoker|search_path=bem_core, pg_temp',
        'bem_core.current_tenant()|bem_core_owner|invoker|search_path=pg_catalog, pg_temp',
        'bem_core.evidence_identity()|bem_core_owner|invoker|search_path=bem_core, pg_catalog, pg_temp',
        'bem_core.forbid_author_change_after_publish()|bem_core_owner|invoker|search_path=bem_core, pg_temp',
        'bem_core.forbid_self_audit()|bem_core_owner|invoker|search_path=bem_core, pg_temp',
        'bem_core.forbid_update_delete()|bem_core_owner|invoker|search_path=bem_core, pg_temp',
        'bem_core.handoff_requires_sha()|bem_core_owner|invoker|search_path=pg_catalog, pg_temp',
        'bem_core.require_at_least_one_author()|bem_core_owner|invoker|search_path=bem_core, pg_temp'];
    v_read    constant text[] := ARRAY[
        'backup_reader|ALLSEQUENCES:bem_control|SELECT',
        'backup_reader|ALLSEQUENCES:bem_core|SELECT',
        'backup_reader|ALLSEQUENCES:bem_engine|SELECT',
        'backup_reader|ALLTABLES:bem_control|SELECT',
        'backup_reader|ALLTABLES:bem_core|SELECT',
        'backup_reader|ALLTABLES:bem_engine|SELECT',
        'backup_reader|DATABASE:bem|CONNECT',
        'backup_reader|DEFSEQUENCES:bem_control|SELECT',
        'backup_reader|DEFSEQUENCES:bem_core|SELECT',
        'backup_reader|DEFSEQUENCES:bem_engine|SELECT',
        'backup_reader|DEFTABLES:bem_control|SELECT',
        'backup_reader|DEFTABLES:bem_core|SELECT',
        'backup_reader|DEFTABLES:bem_engine|SELECT',
        'backup_reader|SCHEMA:bem_control|USAGE',
        'backup_reader|SCHEMA:bem_core|USAGE',
        'backup_reader|SCHEMA:bem_engine|USAGE',
        'bem_backup_admin|DATABASE:bem|CONNECT',
        'bem_backup_admin|SCHEMA:bem_control|USAGE',
        'bem_backup_ctl_owner|SCHEMA:bem_control|USAGE',
        'bem_backup_ctl_owner|TABLE:bem_control.backup_window|SELECT',
        'bem_bootstrap_admin|DATABASE:bem|CONNECT',
        'bem_control_owner|ALLSEQUENCES:bem_core|SELECT',
        'bem_control_owner|ALLTABLES:bem_core|SELECT',
        'bem_control_owner|ALLTABLES:bem_engine|SELECT',
        'bem_control_owner|DEFSEQUENCES:bem_core|SELECT',
        'bem_control_owner|DEFSEQUENCES:bem_engine|SELECT',
        'bem_control_owner|DEFTABLES:bem_core|SELECT',
        'bem_control_owner|DEFTABLES:bem_engine|SELECT',
        'bem_control_owner|SCHEMA:bem_core|USAGE',
        'bem_control_owner|SCHEMA:bem_engine|USAGE',
        'bem_engine_rw|DATABASE:bem|CONNECT',
        'bem_engine_rw|SCHEMA:bem_engine|USAGE',
        'bem_governance|SCHEMA:bem_control|USAGE',
        'bem_kernel_rw|ALLSEQUENCES:bem_core|SELECT',
        'bem_kernel_rw|ALLTABLES:bem_core|SELECT',
        'bem_kernel_rw|DATABASE:bem|CONNECT',
        'bem_kernel_rw|DEFSEQUENCES:bem_core|SELECT',
        'bem_kernel_rw|DEFTABLES:bem_core|SELECT',
        'bem_kernel_rw|SCHEMA:bem_control|USAGE',
        'bem_kernel_rw|SCHEMA:bem_core|USAGE',
        'schema_migrator|DATABASE:bem|CONNECT'];
    v_exec    constant text[] := ARRAY[
        'bem_control.accept_handoff(uuid, uuid, integer, text)|bem_kernel_rw',
        'bem_control.apply_transition(uuid, uuid, integer, text[], text, uuid, text, jsonb, jsonb)|bem_kernel_rw',
        'bem_control.assert_authority(text, uuid)|bem_kernel_rw',
        'bem_control.assert_tenant(uuid)|bem_kernel_rw',
        'bem_control.assign_auditor(uuid, uuid, text, jsonb)|bem_governance',
        'bem_control.backup_window_assert_closed()|bem_backup_admin',
        'bem_control.backup_window_drain()|bem_backup_admin',
        'bem_control.backup_window_lock()|bem_backup_admin',
        'bem_control.backup_window_open(integer)|bem_backup_admin',
        'bem_control.bind_process_instance(uuid, uuid, text)|bem_kernel_rw',
        'bem_control.claim_outbox_batch(integer, interval, text)|bem_kernel_rw',
        'bem_control.create_actor(text, bem_core.provider, uuid, name)|bem_governance',
        'bem_control.create_tenant(uuid, text, text, uuid, jsonb)|bem_governance',
        'bem_control.create_work_item(uuid, uuid, text, text, jsonb)|bem_kernel_rw',
        'bem_control.current_actor_checked(uuid)|bem_kernel_rw',
        'bem_control.data_digest(regclass)|bem_backup_admin',
        'bem_control.data_digest(regclass)|bem_kernel_rw',
        'bem_control.database_digest()|bem_backup_admin',
        'bem_control.database_digest()|bem_kernel_rw',
        'bem_control.dead_letter_outbox_row(uuid, uuid, text)|bem_governance',
        'bem_control.evidence_write(uuid, text, jsonb)|bem_control_owner',
        'bem_control.finish_outbox_row(uuid, bigint, text, text, jsonb)|bem_kernel_rw',
        'bem_control.grant_authority(text, text, uuid)|bem_governance',
        'bem_control.grant_delegation(name, text, text)|bem_governance',
        'bem_control.outbox_retry_limit()|bem_kernel_rw',
        'bem_control.publish_subject(uuid, uuid, uuid, text, text, text, text[], jsonb)|bem_kernel_rw',
        'bem_control.reconcile_unknown_outcome(uuid, uuid, text, jsonb)|bem_governance',
        'bem_control.record_audit_verdict(uuid, uuid, text, text, jsonb)|bem_kernel_rw',
        'bem_control.record_backup_evidence(jsonb)|bem_backup_admin',
        'bem_control.record_evidence(uuid, text, jsonb)|bem_kernel_rw',
        'bem_control.record_handoff(uuid, uuid, integer, jsonb, text)|bem_kernel_rw',
        'bem_control.record_usage(uuid, uuid, integer, text, text, integer, integer, integer, integer, integer, integer, text, text)|bem_kernel_rw',
        'bem_control.release_subject(uuid, uuid, text)|bem_kernel_rw',
        'bem_control.revoke_auditor(uuid, uuid, text, jsonb)|bem_governance',
        'bem_control.revoke_authority(text, text, uuid)|bem_governance',
        'bem_control.revoke_delegation(uuid)|bem_governance',
        'bem_control.schema_digest(regclass)|bem_backup_admin',
        'bem_control.schema_digest(regclass)|bem_kernel_rw',
        'bem_control.set_tenant_membership(uuid, uuid, text, boolean)|bem_kernel_rw'];
    -- Права целиком: вид | объект | получатель | право[*] | выдавший.
    -- У записи прав по умолчанию: DEFAULT | роль | схема | вид |
    -- получатель | право | выдавший. Выдавший — последнее поле с R31
    -- (замечание M-H115-R15-01). Список печатает сверщик раздела
    -- 15.11 из модели прав PostgreSQL 16 и сверяет с каноном.
    v_acl     constant text[] := ARRAY[
        'COLUMN|bem_control.backup_window.closed_at|bem_backup_ctl_owner|UPDATE|bem_control_owner',
        'COLUMN|bem_control.backup_window.locked_at|bem_backup_ctl_owner|UPDATE|bem_control_owner',
        'COLUMN|bem_control.backup_window.locked_by|bem_backup_ctl_owner|UPDATE|bem_control_owner',
        'COLUMN|bem_control.backup_window.locked_xid|bem_backup_ctl_owner|UPDATE|bem_control_owner',
        'COLUMN|bem_control.backup_window.zero_streak|bem_backup_ctl_owner|UPDATE|bem_control_owner',
        'COLUMN|bem_core.actor_authority.revoked_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.actor_delegation.revoked_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.actor_delegation.revoked_by|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.audit_assignment.assigned_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.audit_assignment.assigned_by|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.audit_assignment.revoked_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.command_log.outbox_id|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.command_log.result_revision|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.handoff_packet.accepted_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.handoff_packet.accepted_by|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.attempt_count|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.dead_letter_reason|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.dead_lettered_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.finished_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.lease_epoch|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.send_started_epoch|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.send_policy_version|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.send_policy_idempotent|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.send_runtime_instance|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.leased_by|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.leased_until|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.next_attempt_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.reconciled_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.reconciled_outcome|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.result|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.outbox.status|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.subject.disagreement_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.subject.disagreement_reason|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.subject.head_sha|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.subject.published_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.subject.released_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.subject.released_by|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.user_tenant_membership.revoked_at|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.user_tenant_membership.revoked_by|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.work_item.process_instance_id|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.work_item.revision|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.work_item.status|bem_control_owner|UPDATE|bem_core_owner',
        'COLUMN|bem_core.work_item.updated_at|bem_control_owner|UPDATE|bem_core_owner',
        'DATABASE|bem|backup_reader|CONNECT|bem_core_owner',
        'DATABASE|bem|bem_backup_admin|CONNECT|bem_core_owner',
        'DATABASE|bem|bem_bootstrap_admin|CONNECT|bem_core_owner',
        'DATABASE|bem|bem_core_owner|CONNECT|bem_core_owner',
        'DATABASE|bem|bem_core_owner|CREATE|bem_core_owner',
        'DATABASE|bem|bem_core_owner|TEMPORARY|bem_core_owner',
        'DATABASE|bem|bem_engine_rw|CONNECT|bem_core_owner',
        'DATABASE|bem|bem_kernel_rw|CONNECT|bem_core_owner',
        'DATABASE|bem|schema_migrator|CONNECT|bem_core_owner',
        'DEFAULT|bem_control_owner|bem_control|S|backup_reader|SELECT|bem_control_owner',
        'DEFAULT|bem_control_owner|bem_control|r|backup_reader|SELECT|bem_control_owner',
        'DEFAULT|bem_core_owner|bem_core|S|backup_reader|SELECT|bem_core_owner',
        'DEFAULT|bem_core_owner|bem_core|S|bem_control_owner|SELECT|bem_core_owner',
        'DEFAULT|bem_core_owner|bem_core|S|bem_kernel_rw|SELECT|bem_core_owner',
        'DEFAULT|bem_core_owner|bem_core|r|backup_reader|SELECT|bem_core_owner',
        'DEFAULT|bem_core_owner|bem_core|r|bem_control_owner|SELECT|bem_core_owner',
        'DEFAULT|bem_core_owner|bem_core|r|bem_kernel_rw|SELECT|bem_core_owner',
        'DEFAULT|bem_engine_owner|bem_engine|S|backup_reader|SELECT|bem_engine_owner',
        'DEFAULT|bem_engine_owner|bem_engine|S|bem_control_owner|SELECT|bem_engine_owner',
        'DEFAULT|bem_engine_owner|bem_engine|r|backup_reader|SELECT|bem_engine_owner',
        'DEFAULT|bem_engine_owner|bem_engine|r|bem_control_owner|SELECT|bem_engine_owner',
        'FUNCTION|bem_control.accept_handoff(uuid, uuid, integer, text)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.accept_handoff(uuid, uuid, integer, text)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.apply_transition(uuid, uuid, integer, text[], text, uuid, text, jsonb, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.apply_transition(uuid, uuid, integer, text[], text, uuid, text, jsonb, jsonb)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.assert_authority(text, uuid)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.assert_authority(text, uuid)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.assert_command_identity(bem_core.command_log, uuid, uuid, uuid, text, text, boolean, text)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.assert_tenant(uuid)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.assert_tenant(uuid)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.assign_auditor(uuid, uuid, text, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.assign_auditor(uuid, uuid, text, jsonb)|bem_governance|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.authority_barrier(text)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.backup_window_assert_closed()|bem_backup_admin|EXECUTE|bem_backup_ctl_owner',
        'FUNCTION|bem_control.backup_window_assert_closed()|bem_backup_ctl_owner|EXECUTE|bem_backup_ctl_owner',
        'FUNCTION|bem_control.backup_window_drain()|bem_backup_admin|EXECUTE|bem_backup_ctl_owner',
        'FUNCTION|bem_control.backup_window_drain()|bem_backup_ctl_owner|EXECUTE|bem_backup_ctl_owner',
        'FUNCTION|bem_control.backup_window_lock()|bem_backup_admin|EXECUTE|bem_backup_ctl_owner',
        'FUNCTION|bem_control.backup_window_lock()|bem_backup_ctl_owner|EXECUTE|bem_backup_ctl_owner',
        'FUNCTION|bem_control.backup_window_open(integer)|bem_backup_admin|EXECUTE|bem_backup_ctl_owner',
        'FUNCTION|bem_control.backup_window_open(integer)|bem_backup_ctl_owner|EXECUTE|bem_backup_ctl_owner',
        'FUNCTION|bem_control.bind_process_instance(uuid, uuid, text)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.bind_process_instance(uuid, uuid, text)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.claim_outbox_batch(integer, interval, text)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.claim_outbox_batch(integer, interval, text)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.mark_outbox_send_started(uuid, bigint, text, text)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.mark_outbox_send_started(uuid, bigint, text, text)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.set_outbox_kind_policy(text, boolean, text, text, text)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.set_outbox_kind_policy(text, boolean, text, text, text)|bem_governance|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.record_outbox_fence(uuid, uuid, bigint, text, text, text, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.record_outbox_fence(uuid, uuid, bigint, text, text, text, jsonb)|bem_governance|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.command_fingerprint(uuid, uuid, text, integer, text[], text, text, jsonb, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.create_actor(text, bem_core.provider, uuid, name)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.create_actor(text, bem_core.provider, uuid, name)|bem_governance|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.create_tenant(uuid, text, text, uuid, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.create_tenant(uuid, text, text, uuid, jsonb)|bem_governance|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.create_work_item(uuid, uuid, text, text, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.create_work_item(uuid, uuid, text, text, jsonb)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.current_actor_checked(uuid)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.current_actor_checked(uuid)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.data_digest(regclass)|bem_backup_admin|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.data_digest(regclass)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.data_digest(regclass)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.database_digest()|bem_backup_admin|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.database_digest()|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.database_digest()|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.dead_letter_outbox_row(uuid, uuid, text)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.dead_letter_outbox_row(uuid, uuid, text)|bem_governance|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.evidence_write(uuid, text, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.finish_outbox_row(uuid, bigint, text, text, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.finish_outbox_row(uuid, bigint, text, text, jsonb)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.grant_authority(text, text, uuid)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.grant_authority(text, text, uuid)|bem_governance|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.grant_delegation(name, text, text)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.grant_delegation(name, text, text)|bem_governance|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.lock_subject(uuid, uuid)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.operator_lock_key()|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.outbox_retry_limit()|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.outbox_retry_limit()|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.publish_subject(uuid, uuid, uuid, text, text, text, text[], jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.publish_subject(uuid, uuid, uuid, text, text, text, text[], jsonb)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.reconcile_unknown_outcome(uuid, uuid, text, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.reconcile_unknown_outcome(uuid, uuid, text, jsonb)|bem_governance|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.record_audit_verdict(uuid, uuid, text, text, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.record_audit_verdict(uuid, uuid, text, text, jsonb)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.record_backup_evidence(jsonb)|bem_backup_admin|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.record_backup_evidence(jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.record_evidence(uuid, text, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.record_evidence(uuid, text, jsonb)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.record_handoff(uuid, uuid, integer, jsonb, text)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.record_handoff(uuid, uuid, integer, jsonb, text)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.record_usage(uuid, uuid, integer, text, text, integer, integer, integer, integer, integer, integer, text, text)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.record_usage(uuid, uuid, integer, text, text, integer, integer, integer, integer, integer, integer, text, text)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.release_subject(uuid, uuid, text)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.release_subject(uuid, uuid, text)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.revoke_auditor(uuid, uuid, text, jsonb)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.revoke_auditor(uuid, uuid, text, jsonb)|bem_governance|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.revoke_authority(text, text, uuid)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.revoke_authority(text, text, uuid)|bem_governance|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.revoke_delegation(uuid)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.revoke_delegation(uuid)|bem_governance|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.schema_digest(regclass)|bem_backup_admin|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.schema_digest(regclass)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.schema_digest(regclass)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.service_tenant()|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.set_tenant_membership(uuid, uuid, text, boolean)|bem_control_owner|EXECUTE|bem_control_owner',
        'FUNCTION|bem_control.set_tenant_membership(uuid, uuid, text, boolean)|bem_kernel_rw|EXECUTE|bem_control_owner',
        'SCHEMA|bem_control|backup_reader|USAGE|bem_control_owner',
        'SCHEMA|bem_control|bem_backup_admin|USAGE|bem_control_owner',
        'SCHEMA|bem_control|bem_backup_ctl_owner|USAGE|bem_control_owner',
        'SCHEMA|bem_control|bem_control_owner|CREATE|bem_control_owner',
        'SCHEMA|bem_control|bem_control_owner|USAGE|bem_control_owner',
        'SCHEMA|bem_control|bem_governance|USAGE|bem_control_owner',
        'SCHEMA|bem_control|bem_kernel_rw|USAGE|bem_control_owner',
        'SCHEMA|bem_core|backup_reader|USAGE|bem_core_owner',
        'SCHEMA|bem_core|bem_control_owner|USAGE|bem_core_owner',
        'SCHEMA|bem_core|bem_core_owner|CREATE|bem_core_owner',
        'SCHEMA|bem_core|bem_core_owner|USAGE|bem_core_owner',
        'SCHEMA|bem_core|bem_kernel_rw|USAGE|bem_core_owner',
        'SCHEMA|bem_engine|backup_reader|USAGE|bem_engine_owner',
        'SCHEMA|bem_engine|bem_control_owner|USAGE|bem_engine_owner',
        'SCHEMA|bem_engine|bem_engine_owner|CREATE|bem_engine_owner',
        'SCHEMA|bem_engine|bem_engine_owner|USAGE|bem_engine_owner',
        'SCHEMA|bem_engine|bem_engine_rw|USAGE|bem_engine_owner',
        'SCHEMA|public|pg_database_owner|CREATE|pg_database_owner',
        'SCHEMA|public|pg_database_owner|USAGE|pg_database_owner',
        'TABLE|bem_control.authority_guard|backup_reader|SELECT|bem_control_owner',
        'TABLE|bem_control.outbox_kind_policy|bem_control_owner|DELETE|bem_control_owner',
        'TABLE|bem_control.outbox_kind_policy|bem_control_owner|INSERT|bem_control_owner',
        'TABLE|bem_control.outbox_kind_policy|bem_control_owner|REFERENCES|bem_control_owner',
        'TABLE|bem_control.outbox_kind_policy|bem_control_owner|SELECT|bem_control_owner',
        'TABLE|bem_control.outbox_kind_policy|bem_control_owner|TRIGGER|bem_control_owner',
        'TABLE|bem_control.outbox_kind_policy|bem_control_owner|TRUNCATE|bem_control_owner',
        'TABLE|bem_control.outbox_kind_policy|bem_control_owner|UPDATE|bem_control_owner',
        'TABLE|bem_control.outbox_kind_policy|backup_reader|SELECT|bem_control_owner',
        'TABLE|bem_control.outbox_kind_policy|bem_kernel_rw|SELECT|bem_control_owner',
        'TABLE|bem_control.outbox_send_fence|bem_control_owner|DELETE|bem_control_owner',
        'TABLE|bem_control.outbox_send_fence|bem_control_owner|INSERT|bem_control_owner',
        'TABLE|bem_control.outbox_send_fence|bem_control_owner|REFERENCES|bem_control_owner',
        'TABLE|bem_control.outbox_send_fence|bem_control_owner|SELECT|bem_control_owner',
        'TABLE|bem_control.outbox_send_fence|bem_control_owner|TRIGGER|bem_control_owner',
        'TABLE|bem_control.outbox_send_fence|bem_control_owner|TRUNCATE|bem_control_owner',
        'TABLE|bem_control.outbox_send_fence|bem_control_owner|UPDATE|bem_control_owner',
        'TABLE|bem_control.outbox_send_fence|backup_reader|SELECT|bem_control_owner',
        'TABLE|bem_control.authority_guard|bem_control_owner|DELETE|bem_control_owner',
        'TABLE|bem_control.authority_guard|bem_control_owner|INSERT|bem_control_owner',
        'TABLE|bem_control.authority_guard|bem_control_owner|REFERENCES|bem_control_owner',
        'TABLE|bem_control.authority_guard|bem_control_owner|SELECT|bem_control_owner',
        'TABLE|bem_control.authority_guard|bem_control_owner|TRIGGER|bem_control_owner',
        'TABLE|bem_control.authority_guard|bem_control_owner|TRUNCATE|bem_control_owner',
        'TABLE|bem_control.authority_guard|bem_control_owner|UPDATE|bem_control_owner',
        'TABLE|bem_control.backup_window|backup_reader|SELECT|bem_control_owner',
        'TABLE|bem_control.backup_window|bem_backup_ctl_owner|SELECT|bem_control_owner',
        'TABLE|bem_control.backup_window|bem_control_owner|DELETE|bem_control_owner',
        'TABLE|bem_control.backup_window|bem_control_owner|INSERT|bem_control_owner',
        'TABLE|bem_control.backup_window|bem_control_owner|REFERENCES|bem_control_owner',
        'TABLE|bem_control.backup_window|bem_control_owner|SELECT|bem_control_owner',
        'TABLE|bem_control.backup_window|bem_control_owner|TRIGGER|bem_control_owner',
        'TABLE|bem_control.backup_window|bem_control_owner|TRUNCATE|bem_control_owner',
        'TABLE|bem_control.backup_window|bem_control_owner|UPDATE|bem_control_owner',
        'TABLE|bem_core.actor_authority|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.actor_authority|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.actor_authority|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.actor_authority|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.actor_authority|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.actor_authority|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.actor_authority|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.actor_authority|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.actor_authority|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.actor_authority|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.actor_authority|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.actor_delegation|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.actor_delegation|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.actor_delegation|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.actor_delegation|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.actor_delegation|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.actor_delegation|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.actor_delegation|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.actor_delegation|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.actor_delegation|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.actor_delegation|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.actor_delegation|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.actor|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.actor|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.actor|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.actor|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.actor|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.actor|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.actor|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.actor|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.actor|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.actor|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.actor|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.audit_assignment|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.audit_assignment|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.audit_assignment|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.audit_assignment|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.audit_assignment|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.audit_assignment|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.audit_assignment|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.audit_assignment|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.audit_assignment|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.audit_assignment|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.audit_assignment|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.audit_record|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.audit_record|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.audit_record|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.audit_record|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.audit_record|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.audit_record|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.audit_record|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.audit_record|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.audit_record|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.audit_record|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.audit_record|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.command_log|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.command_log|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.command_log|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.command_log|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.command_log|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.command_log|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.command_log|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.command_log|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.command_log|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.command_log|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.command_log|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.evidence|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.evidence|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.evidence|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.evidence|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.evidence|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.evidence|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.evidence|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.evidence|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.evidence|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.evidence|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.evidence|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.handoff_packet|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.handoff_packet|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.handoff_packet|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.handoff_packet|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.handoff_packet|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.handoff_packet|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.handoff_packet|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.handoff_packet|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.handoff_packet|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.handoff_packet|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.handoff_packet|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.outbox|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.outbox|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.outbox|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.outbox|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.outbox|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.outbox|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.outbox|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.outbox|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.outbox|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.outbox|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.outbox|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.schema_migration|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.schema_migration|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.schema_migration|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.schema_migration|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.schema_migration|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.schema_migration|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.schema_migration|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.schema_migration|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.schema_migration|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.schema_migration|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.subject_author|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.subject_author|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.subject_author|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.subject_author|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.subject_author|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.subject_author|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.subject_author|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.subject_author|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.subject_author|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.subject_author|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.subject_author|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.subject|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.subject|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.subject|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.subject|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.subject|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.subject|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.subject|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.subject|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.subject|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.subject|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.subject|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.tenant|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.tenant|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.tenant|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.tenant|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.tenant|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.tenant|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.tenant|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.tenant|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.tenant|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.tenant|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.tenant|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.usage_record|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.usage_record|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.usage_record|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.usage_record|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.usage_record|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.usage_record|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.usage_record|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.usage_record|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.usage_record|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.usage_record|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.usage_record|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.user_tenant_membership|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.user_tenant_membership|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.user_tenant_membership|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.user_tenant_membership|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.user_tenant_membership|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.user_tenant_membership|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.user_tenant_membership|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.user_tenant_membership|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.user_tenant_membership|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.user_tenant_membership|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.user_tenant_membership|bem_kernel_rw|SELECT|bem_core_owner',
        'TABLE|bem_core.work_item|backup_reader|SELECT|bem_core_owner',
        'TABLE|bem_core.work_item|bem_control_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.work_item|bem_control_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.work_item|bem_core_owner|DELETE|bem_core_owner',
        'TABLE|bem_core.work_item|bem_core_owner|INSERT|bem_core_owner',
        'TABLE|bem_core.work_item|bem_core_owner|REFERENCES|bem_core_owner',
        'TABLE|bem_core.work_item|bem_core_owner|SELECT|bem_core_owner',
        'TABLE|bem_core.work_item|bem_core_owner|TRIGGER|bem_core_owner',
        'TABLE|bem_core.work_item|bem_core_owner|TRUNCATE|bem_core_owner',
        'TABLE|bem_core.work_item|bem_core_owner|UPDATE|bem_core_owner',
        'TABLE|bem_core.work_item|bem_kernel_rw|SELECT|bem_core_owner'
    ];
    v_row   text;
    v_got   text;
    v_who   text;
    v_obj   text;
    v_priv  text;
    v_okind text;
    v_oname text;
    v_sig   text;
    v_path  text;
    v_name  text;
    v_oid   oid;
    v_cnt   integer;
    v_ok    boolean;
    v_sha_req boolean;
    v_want  text;
    v_acl_got text[];
BEGIN
    -- 1. Признаки каждой роли пакета совпадают с объявленными целиком.
    --    Не «нет суперпользователя», а все девять полей сразу: роль,
    --    у которой поменяли один признак, — это другая роль.
    FOREACH v_row IN ARRAY v_roles LOOP
        v_name := split_part(v_row, '|', 1);
        SELECT r.rolname || '|'
               || CASE WHEN r.rolcanlogin     THEN 'yes' ELSE 'no' END || '|'
               || CASE WHEN r.rolsuper        THEN 'yes' ELSE 'no' END || '|'
               || CASE WHEN r.rolcreatedb     THEN 'yes' ELSE 'no' END || '|'
               || CASE WHEN r.rolcreaterole   THEN 'yes' ELSE 'no' END || '|'
               || CASE WHEN r.rolreplication  THEN 'yes' ELSE 'no' END || '|'
               || CASE WHEN r.rolbypassrls    THEN 'yes' ELSE 'no' END || '|'
               || CASE WHEN r.rolinherit      THEN 'yes' ELSE 'no' END || '|'
               || r.rolconnlimit
          INTO v_got
          FROM pg_roles r WHERE r.rolname = v_name;
        IF v_got IS NULL THEN
            RAISE EXCEPTION 'FINAL_ROLE_ATTRS_MISMATCH: роли нет: %', v_name;
        END IF;
        IF v_got <> v_row THEN
            RAISE EXCEPTION 'FINAL_ROLE_ATTRS_MISMATCH: объявлено % , найдено %',
                            v_row, v_got;
        END IF;
    END LOOP;

    -- 2. Граф членств целиком: и каждая объявленная строка есть, и ни
    --    одной сверх объявленных. Выдавшим обязан быть начальный
    --    суперпользователь кластера — роль с номером 10. PostgreSQL 16
    --    записывает выдачу от любого суперпользователя именно ему, а не
    --    тому, кто выполнил команду (замечание M-H113-R13-03).
    FOREACH v_row IN ARRAY v_members LOOP
        SELECT g.rolname || '|' || s.rolname || '|BOOTSTRAP_SUPERUSER|'
               || CASE WHEN m.admin_option   THEN 'yes' ELSE 'no' END || '|'
               || CASE WHEN m.inherit_option THEN 'yes' ELSE 'no' END || '|'
               || CASE WHEN m.set_option     THEN 'yes' ELSE 'no' END
          INTO v_got
          FROM pg_auth_members m
          JOIN pg_roles g ON g.oid = m.roleid
          JOIN pg_roles s ON s.oid = m.member
         WHERE g.rolname = split_part(v_row, '|', 1)
           AND s.rolname = split_part(v_row, '|', 2)
           AND m.grantor = 10;
        IF v_got IS NULL THEN
            RAISE EXCEPTION 'FINAL_MEMBERSHIP_MISMATCH: членства нет или выдал не начальный суперпользователь: %',
                            v_row;
        END IF;
        IF v_got <> v_row THEN
            RAISE EXCEPTION 'FINAL_MEMBERSHIP_MISMATCH: объявлено % , найдено %',
                            v_row, v_got;
        END IF;
    END LOOP;
    SELECT count(*) INTO v_cnt
      FROM pg_auth_members m
      JOIN pg_roles g ON g.oid = m.roleid
      JOIN pg_roles s ON s.oid = m.member
     WHERE (s.rolname = ANY (SELECT split_part(x, '|', 1) FROM unnest(v_roles) x)
            OR g.rolname = ANY (SELECT split_part(x, '|', 1) FROM unnest(v_roles) x))
       AND (g.rolname || '|' || s.rolname) <> ALL (
            SELECT split_part(x, '|', 1) || '|' || split_part(x, '|', 2) FROM unnest(v_members) x);
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'FINAL_MEMBERSHIP_MISMATCH: лишних членств: %', v_cnt;
    END IF;

    -- 3. Пароль, срок годности и настройки сеанса. Ни одна роль пакета
    --    не имеет пароля: вход настраивается сертификатом клиента, а
    --    строки pg_hba.conf пишет администратор отдельно (раздел 25.2).
    --    Срока годности и настроек сеанса нет ни у одной роли: строка
    --    вида «путь поиска по умолчанию» меняет то, какую функцию
    --    вызовет чужой код, не трогая ни одного права.
    FOREACH v_row IN ARRAY v_secrets LOOP
        v_name := split_part(v_row, '|', 1);
        SELECT CASE WHEN r.rolpassword IS NULL THEN 'нет' ELSE 'задан' END || '|'
               || CASE WHEN r.rolvaliduntil IS NULL THEN 'нет' ELSE 'задан' END || '|'
               || CASE WHEN NOT EXISTS (SELECT 1 FROM pg_db_role_setting s WHERE s.setrole = r.oid) THEN 'нет' ELSE 'задан' END
          INTO v_got
          FROM pg_authid r WHERE r.rolname = v_name;
        IF v_got IS NULL THEN
            RAISE EXCEPTION 'FINAL_ROLE_SECRETS_MISMATCH: роли нет: %', v_name;
        END IF;
        IF v_got <> 'нет|нет|нет' THEN
            RAISE EXCEPTION
              'FINAL_ROLE_SECRETS_MISMATCH: у роли % пароль, срок годности или настройка сеанса: %',
              v_name, v_got;
        END IF;
    END LOOP;

    -- 4. Входить умеют ровно объявленные роли и никто сверх них.
    FOREACH v_row IN ARRAY v_roles LOOP
        v_name := split_part(v_row, '|', 1);
        SELECT rolcanlogin INTO v_ok FROM pg_roles WHERE rolname = v_name;
        IF v_ok AND NOT (v_name = ANY (v_login)) THEN
            RAISE EXCEPTION 'FINAL_EXTRA_LOGIN_ROLE: роль умеет входить сверх договора: %', v_name;
        END IF;
        IF NOT v_ok AND v_name = ANY (v_login) THEN
            RAISE EXCEPTION 'FINAL_EXTRA_LOGIN_ROLE: объявленная входная роль входить не умеет: %', v_name;
        END IF;
    END LOOP;

    -- 5. Защита строк включена и включена принудительно. Без второго
    --    признака владелец таблицы читает её мимо политики.
    FOREACH v_row IN ARRAY v_rls LOOP
        SELECT c.relrowsecurity AND c.relforcerowsecurity INTO v_ok
          FROM pg_class c WHERE c.oid = v_row::regclass;
        IF v_ok IS DISTINCT FROM true THEN
            RAISE EXCEPTION 'FINAL_RLS_MISMATCH: защита строк не включена целиком: %', v_row;
        END IF;
    END LOOP;

    -- 6. Политика целиком, все семь полей. Получатели и выражения
    --    решают, какие строки роль видит и какие меняет; без них
    --    проверка ловила только переименование. Порядок получателей
    --    приводится к возрастанию: в каталоге он произвольный.
    FOREACH v_row IN ARRAY v_policy LOOP
        SELECT p.schemaname || '.' || p.tablename || '|' || p.policyname
               || '|' || p.cmd
               || '|' || CASE WHEN p.permissive = 'PERMISSIVE'
                                       THEN 'PERMISSIVE' ELSE 'RESTRICTIVE' END
               || '|' || COALESCE((SELECT string_agg(x, ',' ORDER BY x COLLATE "C")
                                     FROM unnest(p.roles) AS x), '<нет>')
               || '|' || replace(COALESCE(p.qual, '<нет>'), 'bem_core.', '')
               || '|' || replace(COALESCE(p.with_check, '<нет>'), 'bem_core.', '')
          INTO v_got
          FROM pg_policies p
         WHERE p.schemaname || '.' || p.tablename = split_part(v_row, '|', 1)
           AND p.policyname = split_part(v_row, '|', 2);
        IF v_got IS DISTINCT FROM v_row THEN
            RAISE EXCEPTION 'FINAL_POLICY_MISMATCH: объявлено % , найдено %',
                            v_row, coalesce(v_got, 'политики нет');
        END IF;
    END LOOP;
    SELECT count(*) INTO v_cnt FROM pg_policies p
     WHERE p.schemaname IN ('bem_core', 'bem_control', 'bem_engine')
       AND (p.schemaname || '.' || p.tablename || '|' || p.policyname) <> ALL (
            SELECT split_part(x, '|', 1) || '|' || split_part(x, '|', 2) FROM unnest(v_policy) x);
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'FINAL_POLICY_MISMATCH: лишних политик: %', v_cnt;
    END IF;

    -- 7. Триггеры целиком, а не по имени. Отпечаток из одиннадцати
    --    полей сверяется в обе стороны: не хватает — отказ, лишний
    --    триггер на управляемой таблице — тоже отказ. Имена схем
    --    берутся из pg_namespace, а не приведением к regclass:
    --    приведение зависит от search_path сеанса.
    SELECT COALESCE(string_agg(fp, E'\n' ORDER BY fp COLLATE "C"), '')
      INTO v_got
      FROM (
        SELECT tn.nspname || '.' || tc.relname || '|' || tg.tgname
               || '|' || tg.tgtype
               || '|' || COALESCE((
                        SELECT string_agg(a.attname::text, ',' ORDER BY u.ord)
                          FROM unnest(tg.tgattr::smallint[]) WITH ORDINALITY AS u(attnum, ord)
                          JOIN pg_attribute a
                            ON a.attrelid = tg.tgrelid AND a.attnum = u.attnum
                      ), '')
               || '|' || fn.nspname || '.' || fp.proname || '()'
               || '|' || tg.tgenabled::text
               || '|' || CASE WHEN tg.tgconstraint <> 0 THEN 't' ELSE 'f' END
               || '|' || CASE WHEN tg.tgdeferrable     THEN 't' ELSE 'f' END
               || '|' || CASE WHEN tg.tginitdeferred   THEN 't' ELSE 'f' END
               || '|' || CASE WHEN tg.tgqual IS NOT NULL THEN 't' ELSE 'f' END
               || '|' || tg.tgnargs AS fp
          FROM pg_trigger tg
          JOIN pg_class     tc ON tc.oid = tg.tgrelid
          JOIN pg_namespace tn ON tn.oid = tc.relnamespace
          JOIN pg_proc      fp ON fp.oid = tg.tgfoid
          JOIN pg_namespace fn ON fn.oid = fp.pronamespace
         WHERE NOT tg.tgisinternal
           AND tn.nspname = 'bem_core'
           AND tc.relname IN ('audit_record', 'command_log', 'evidence',
                              'handoff_packet', 'subject', 'subject_author')
      ) q;

    -- Мостовой триггер ожидается тогда и только тогда, когда столбец
    -- суммы пакета передачи ещё необязателен.
    SELECT a.attnotnull INTO v_ok
      FROM pg_attribute a
     WHERE a.attrelid = 'bem_core.handoff_packet'::regclass
       AND a.attname  = 'packet_sha256'
       AND NOT a.attisdropped;
    IF v_ok IS NULL THEN
        RAISE EXCEPTION
          'FINAL_TRIGGER_MISMATCH: нет столбца bem_core.handoff_packet.packet_sha256';
    END IF;
    v_sha_req := v_ok;

    SELECT COALESCE(string_agg(x, E'\n' ORDER BY x COLLATE "C"), '')
      INTO v_want
      FROM unnest(CASE WHEN v_ok THEN v_trigger
                       ELSE v_trigger || v_trigger_legacy END) AS x;

    IF v_got <> v_want THEN
        RAISE EXCEPTION
          'FINAL_TRIGGER_MISMATCH: ожидалось %L, получено %L', v_want, v_got;
    END IF;

    -- 7а. Определение каждого триггера целиком (замечание
    --     C-H115-R15-01). Отпечаток шага 7 знает об условии WHEN
    --     только «есть или нет», и WHEN (true) его проходил. Здесь
    --     сверяются текст условия, байты аргументов и строка
    --     pg_get_triggerdef. Путь поиска закреплён: иначе имена схем в
    --     строке зависят от сеанса. Мостовой триггер ожидается при том
    --     же условии, что и в шаге 7.
    v_path := current_setting('search_path');
    PERFORM set_config('search_path', 'pg_catalog, pg_temp', true);
    SELECT COALESCE(string_agg(fp, E'\n' ORDER BY fp COLLATE "C"), '')
      INTO v_got
      FROM (
        SELECT tn.nspname || '.' || tc.relname || '|' || tg.tgname
               || '|' || COALESCE(substring(td.d FROM ' WHEN \((.*)\) EXECUTE FUNCTION '), '')
               || '|' || encode(tg.tgargs, 'hex')
               || '|' || td.d AS fp
          FROM pg_trigger tg
          JOIN pg_class     tc ON tc.oid = tg.tgrelid
          JOIN pg_namespace tn ON tn.oid = tc.relnamespace
          CROSS JOIN LATERAL (SELECT regexp_replace(pg_get_triggerdef(tg.oid, true), '\s+', ' ', 'g') AS d) AS td
         WHERE NOT tg.tgisinternal
           AND tn.nspname = 'bem_core'
           AND tc.relname IN ('audit_record', 'command_log', 'evidence',
                              'handoff_packet', 'subject', 'subject_author')
      ) q;
    PERFORM set_config('search_path', v_path, true);

    SELECT COALESCE(string_agg(x, E'\n' ORDER BY x COLLATE "C"), '')
      INTO v_want
      FROM unnest(CASE WHEN v_ok THEN v_trigger_def
                       ELSE v_trigger_def || v_trigger_def_legacy END) AS x;

    IF v_got <> v_want THEN
        RAISE EXCEPTION
          'FINAL_TRIGGER_MISMATCH: определения: ожидалось %L, получено %L', v_want, v_got;
    END IF;

    -- 8. Владелец, режим исполнения и весь proconfig каждой функции.
    --    Функция с правами владельца и незакреплённым путём поиска —
    --    открытая дверь: вызывающий подставляет свою схему и подменяет
    --    вызов внутри чужого тела. Но путь поиска не единственная
    --    настройка: прежняя проверка читала из proconfig только его и
    --    любую вторую настройку пропускала молча.
    v_path := current_setting('search_path');
    PERFORM set_config('search_path', 'pg_catalog', true);
    FOREACH v_row IN ARRAY v_func LOOP
        v_sig := split_part(v_row, '|', 1);
        -- H1.22, дефект D6 живого прогона R41: функцию мостового триггера
        -- создаёт и удаляет только 02. Когда packet_sha256 обязателен,
        -- её не должно быть совсем, а не «может не быть».
        IF v_sig = 'bem_core.handoff_requires_sha()' AND v_sha_req THEN
            IF EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                        WHERE n.nspname = 'bem_core' AND p.proname = 'handoff_requires_sha') THEN
                RAISE EXCEPTION 'FINAL_FUNCTION_OWNER_MISMATCH: функция % должна отсутствовать: packet_sha256 уже обязателен', v_sig;
            END IF;
            CONTINUE;
        END IF;
        SELECT o.rolname || '|'
               || CASE WHEN p.prosecdef THEN 'definer' ELSE 'invoker' END || '|'
               || coalesce((SELECT string_agg(c, ';' ORDER BY c COLLATE "C")
                              FROM unnest(p.proconfig) c), 'none')
          INTO v_got
          FROM pg_proc p
          JOIN pg_namespace n ON n.oid = p.pronamespace
          JOIN pg_roles o ON o.oid = p.proowner
         WHERE n.nspname || '.' || p.proname || '('
               || oidvectortypes(p.proargtypes) || ')' = v_sig;
        IF v_got IS NULL THEN
            RAISE EXCEPTION 'FINAL_FUNCTION_OWNER_MISMATCH: функции с такой подписью нет: %', v_sig;
        END IF;
        IF v_got <> substr(v_row, length(v_sig) + 2) THEN
            RAISE EXCEPTION 'FINAL_FUNCTION_OWNER_MISMATCH: объявлено % , найдено %|%',
                            v_row, v_sig, v_got;
        END IF;
    END LOOP;
    PERFORM set_config('search_path', v_path, true);

    -- 9. Итоговые права: каждая обязательная строка чтения выдана и
    --    каждый обязательный вызов выдан точному получателю. Списки
    --    посчитаны по всему пакету, включая файл 04, — в отличие от
    --    самопроверки файла 01, которая файла 04 ещё не видела.
    FOREACH v_row IN ARRAY v_read LOOP
        v_who   := split_part(v_row, '|', 1);
        v_obj   := split_part(v_row, '|', 2);
        v_priv  := split_part(v_row, '|', 3);
        v_okind := split_part(v_obj, ':', 1);
        v_oname := split_part(v_obj, ':', 2);
        IF v_okind = 'DATABASE' THEN
            v_ok := has_database_privilege(v_who, v_oname, v_priv);
        ELSIF v_okind = 'SCHEMA' THEN
            v_ok := has_schema_privilege(v_who, v_oname, v_priv);
        ELSIF v_okind = 'TABLE' THEN
            v_ok := has_table_privilege(v_who, v_oname::regclass, v_priv);
        ELSIF v_okind = 'DEFTABLES' OR v_okind = 'DEFSEQUENCES' THEN
            v_ok := EXISTS (
                SELECT 1 FROM pg_default_acl d
                  JOIN pg_namespace n ON n.oid = d.defaclnamespace
                  CROSS JOIN LATERAL aclexplode(d.defaclacl) a
                  JOIN pg_roles r ON r.oid = a.grantee
                 WHERE n.nspname = v_oname
                   AND d.defaclobjtype = CASE WHEN v_okind = 'DEFTABLES'
                                              THEN 'r' ELSE 'S' END
                   AND r.rolname = v_who
                   AND a.privilege_type = v_priv);
        ELSIF v_okind = 'ALLTABLES' OR v_okind = 'ALLSEQUENCES' THEN
            SELECT count(*) INTO v_cnt
              FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = v_oname
               AND ((v_okind = 'ALLTABLES'    AND c.relkind IN ('r', 'p'))
                 OR (v_okind = 'ALLSEQUENCES' AND c.relkind = 'S'));
            IF v_cnt = 0 THEN
                v_ok := EXISTS (
                    SELECT 1 FROM pg_default_acl d
                      JOIN pg_namespace n ON n.oid = d.defaclnamespace
                      CROSS JOIN LATERAL aclexplode(d.defaclacl) a
                      JOIN pg_roles r ON r.oid = a.grantee
                     WHERE n.nspname = v_oname
                       AND d.defaclobjtype = CASE WHEN v_okind = 'ALLTABLES'
                                                  THEN 'r' ELSE 'S' END
                       AND r.rolname = v_who
                       AND a.privilege_type = v_priv);
            ELSE
                v_ok := NOT EXISTS (
                    SELECT 1 FROM pg_class c
                      JOIN pg_namespace n ON n.oid = c.relnamespace
                     WHERE n.nspname = v_oname
                       AND ((v_okind = 'ALLTABLES'    AND c.relkind IN ('r', 'p'))
                         OR (v_okind = 'ALLSEQUENCES' AND c.relkind = 'S'))
                       AND NOT (CASE WHEN v_okind = 'ALLTABLES'
                                     THEN has_table_privilege(v_who, c.oid, v_priv)
                                     ELSE has_sequence_privilege(v_who, c.oid, v_priv)
                                END));
            END IF;
        ELSE
            v_ok := false;
        END IF;
        IF NOT v_ok THEN
            RAISE EXCEPTION 'FINAL_ACL_MISMATCH: обязательного права чтения нет: %', v_row;
        END IF;
    END LOOP;

    v_path := current_setting('search_path');
    PERFORM set_config('search_path', 'pg_catalog', true);
    FOREACH v_row IN ARRAY v_exec LOOP
        v_sig := split_part(v_row, '|', 1);
        v_who := split_part(v_row, '|', 2);
        SELECT p.oid INTO v_oid
          FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname || '.' || p.proname || '('
               || oidvectortypes(p.proargtypes) || ')' = v_sig;
        IF v_oid IS NULL THEN
            RAISE EXCEPTION 'FINAL_ACL_MISMATCH: функции с такой подписью нет: %', v_sig;
        END IF;
        IF NOT has_function_privilege(v_who, v_oid, 'EXECUTE') THEN
            RAISE EXCEPTION 'FINAL_ACL_MISMATCH: обязательного вызова нет: % -> %', v_sig, v_who;
        END IF;
    END LOOP;
    PERFORM set_config('search_path', v_path, true);

    -- 10. Права доступа целиком и в обе стороны: и каждое объявленное
    --     право выдано, и ни одного права сверх договора нет. Шаг 9
    --     односторонний по устройству — он ищет нужное и лишнего не
    --     видит. Так у PUBLIC осталось право TEMPORARY на рабочую базу,
    --     и ни один сверщик этого не показал (замечание M-H114-R14-02).
    --
    --     Системные схемы исключены, а рабочие НЕ перечислены поимённо:
    --     право, выданное в неожиданной схеме, обязано попасть в разницу,
    --     а не выпасть из рассмотрения вместе со схемой.
    --
    --     Звёздочка после права означает право передавать его дальше.
    --     В каноне такой выдачи нет ни одной, поэтому любая звёздочка
    --     здесь — лишнее право.
    --
    --     R31 (замечание M-H115-R15-01). Последнее поле строки — кто
    --     выдал право. Одно и то же право одному получателю, выданное
    --     двумя разными ролями, — это две записи каталога и две строки
    --     здесь. Сравнение идёт с учётом повторов: EXCEPT сводил
    --     одинаковые строки в одну, и повтор проходил молча.
    v_path := current_setting('search_path');
    PERFORM set_config('search_path', 'pg_catalog', true);
    WITH nsp AS (
        SELECT oid, nspname FROM pg_namespace
         WHERE nspname NOT IN ('pg_catalog', 'information_schema')
           AND nspname NOT LIKE 'pg\_toast%'
           AND nspname NOT LIKE 'pg\_temp%'
    ), got AS (
        SELECT 'SCHEMA|' || n.nspname || '|'
               || coalesce(g.rolname, 'PUBLIC') || '|' || a.privilege_type
               || CASE WHEN a.is_grantable THEN '*' ELSE '' END
               || '|' || coalesce(gr.rolname, a.grantor::text) AS r
          FROM nsp n
          JOIN pg_namespace pn ON pn.oid = n.oid
          CROSS JOIN LATERAL aclexplode(pn.nspacl) a
          LEFT JOIN pg_roles g ON g.oid = a.grantee
          LEFT JOIN pg_roles gr ON gr.oid = a.grantor
        UNION ALL
        SELECT 'DATABASE|' || d.datname || '|'
               || coalesce(g.rolname, 'PUBLIC') || '|' || a.privilege_type
               || CASE WHEN a.is_grantable THEN '*' ELSE '' END
               || '|' || coalesce(gr.rolname, a.grantor::text)
          FROM pg_database d
          CROSS JOIN LATERAL aclexplode(d.datacl) a
          LEFT JOIN pg_roles g ON g.oid = a.grantee
          LEFT JOIN pg_roles gr ON gr.oid = a.grantor
         WHERE d.datname = current_database()
        UNION ALL
        SELECT CASE WHEN c.relkind = 'S' THEN 'SEQUENCE|' ELSE 'TABLE|' END
               || n.nspname || '.' || c.relname || '|'
               || coalesce(g.rolname, 'PUBLIC') || '|' || a.privilege_type
               || CASE WHEN a.is_grantable THEN '*' ELSE '' END
               || '|' || coalesce(gr.rolname, a.grantor::text)
          FROM pg_class c
          JOIN nsp n ON n.oid = c.relnamespace
          CROSS JOIN LATERAL aclexplode(c.relacl) a
          LEFT JOIN pg_roles g ON g.oid = a.grantee
          LEFT JOIN pg_roles gr ON gr.oid = a.grantor
         WHERE c.relkind IN ('r', 'p', 'S', 'v', 'm', 'f')
        UNION ALL
        SELECT 'COLUMN|' || n.nspname || '.' || c.relname || '.' || att.attname || '|'
               || coalesce(g.rolname, 'PUBLIC') || '|' || a.privilege_type
               || CASE WHEN a.is_grantable THEN '*' ELSE '' END
               || '|' || coalesce(gr.rolname, a.grantor::text)
          FROM pg_attribute att
          JOIN pg_class c ON c.oid = att.attrelid
          JOIN nsp n ON n.oid = c.relnamespace
          CROSS JOIN LATERAL aclexplode(att.attacl) a
          LEFT JOIN pg_roles g ON g.oid = a.grantee
          LEFT JOIN pg_roles gr ON gr.oid = a.grantor
        UNION ALL
        SELECT 'FUNCTION|' || n.nspname || '.' || p.proname
               || '(' || oidvectortypes(p.proargtypes) || ')|'
               || coalesce(g.rolname, 'PUBLIC') || '|' || a.privilege_type
               || CASE WHEN a.is_grantable THEN '*' ELSE '' END
               || '|' || coalesce(gr.rolname, a.grantor::text)
          FROM pg_proc p
          JOIN nsp n ON n.oid = p.pronamespace
          CROSS JOIN LATERAL aclexplode(p.proacl) a
          LEFT JOIN pg_roles g ON g.oid = a.grantee
          LEFT JOIN pg_roles gr ON gr.oid = a.grantor
        UNION ALL
        SELECT 'DEFAULT|' || o.rolname || '|' || coalesce(dn.nspname, '-') || '|'
               || d.defaclobjtype::text || '|'
               || coalesce(g.rolname, 'PUBLIC') || '|' || a.privilege_type
               || CASE WHEN a.is_grantable THEN '*' ELSE '' END
               || '|' || coalesce(gr.rolname, a.grantor::text)
          FROM pg_default_acl d
          JOIN pg_roles o ON o.oid = d.defaclrole
          LEFT JOIN pg_namespace dn ON dn.oid = d.defaclnamespace
          CROSS JOIN LATERAL aclexplode(d.defaclacl) a
          LEFT JOIN pg_roles g ON g.oid = a.grantee
          LEFT JOIN pg_roles gr ON gr.oid = a.grantor
    )
    SELECT coalesce(array_agg(r ORDER BY r COLLATE "C"), ARRAY[]::text[])
      INTO v_acl_got FROM got;
    PERFORM set_config('search_path', v_path, true);

    -- Сравнение с учётом повторов: у каждой строки считается, сколько
    -- раз она стоит в каталоге и сколько в договоре. Лишнее — где в
    -- каталоге больше, недостающее — где больше в договоре. Число
    -- после x в отказе — на сколько разошлись.
    SELECT count(*), left(coalesce(string_agg(x.r || ' x' || (x.n_got - x.n_want), ', '
                                              ORDER BY x.r COLLATE "C"), ''), 600)
      INTO v_cnt, v_got
      FROM (SELECT coalesce(g.r, w.r) AS r, coalesce(g.n, 0) AS n_got, coalesce(w.n, 0) AS n_want
              FROM (SELECT r, count(*) AS n FROM unnest(v_acl_got) AS r GROUP BY r) g
              FULL JOIN (SELECT r, count(*) AS n FROM unnest(v_acl) AS r GROUP BY r) w
                ON w.r = g.r) x
     WHERE x.n_got > x.n_want;
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'FINAL_ACL_SURPLUS: прав сверх договора %: %', v_cnt, v_got;
    END IF;
    SELECT count(*), left(coalesce(string_agg(x.r || ' x' || (x.n_want - x.n_got), ', '
                                              ORDER BY x.r COLLATE "C"), ''), 600)
      INTO v_cnt, v_got
      FROM (SELECT coalesce(g.r, w.r) AS r, coalesce(g.n, 0) AS n_got, coalesce(w.n, 0) AS n_want
              FROM (SELECT r, count(*) AS n FROM unnest(v_acl_got) AS r GROUP BY r) g
              FULL JOIN (SELECT r, count(*) AS n FROM unnest(v_acl) AS r GROUP BY r) w
                ON w.r = g.r) x
     WHERE x.n_want > x.n_got;
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'FINAL_ACL_MISSING: объявленных прав нет %: %', v_cnt, v_got;
    END IF;

    -- 11. Остатков окна мигратора нет: ни одной сессии, ни одного
    --     членства, вход закрыт. Обёртка это уже проверяла, но её
    --     проверка шла до файла 04; здесь состояние читается заново и
    --     последним.
    SELECT count(*) INTO v_cnt
      FROM pg_stat_activity a JOIN pg_roles r ON r.oid = a.usesysid
     WHERE r.rolname = 'schema_migrator';
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'FINAL_MIGRATOR_RESIDUE: живых сессий мигратора: %', v_cnt;
    END IF;
    SELECT count(*) INTO v_cnt
      FROM pg_auth_members m JOIN pg_roles s ON s.oid = m.member
     WHERE s.rolname = 'schema_migrator';
    IF v_cnt <> 0 THEN
        RAISE EXCEPTION 'FINAL_MIGRATOR_RESIDUE: членств у мигратора: %', v_cnt;
    END IF;
    SELECT rolcanlogin INTO v_ok FROM pg_roles WHERE rolname = 'schema_migrator';
    IF v_ok THEN
        RAISE EXCEPTION 'FINAL_MIGRATOR_RESIDUE: вход мигратора открыт';
    END IF;
END
$$;

-- Z-EXT-01 (аудит Z3 M-Z3-01): тела функций расширения совпадают с db/02_zavod_ext_01.sql.
-- У каждого имени ровно одна функция в bem_control; лишняя перегрузка или подменённое тело — отказ.
DO $zavod_fp$
DECLARE
    r     record;
    v_cnt integer;
    v_got text;
BEGIN
    FOR r IN SELECT * FROM (VALUES
        ('publish_subject', 'e834b723066588f462d3208af12eb9c4e8e06c125640eb37d7e9caf0df68a996'),
        ('release_subject', '9672b176c80839b9286f4a8e20b4fadd54d921827f5eb5075bf0966a4a586bee'),
        ('reconcile_unknown_outcome', '1e1ecfe0d412fa3e1f35ec605ff31d0ab6d8971af753b4fac1829ffc2e84a296'),
        ('claim_outbox_batch', '2f99d0cf2e2e42edb0e613002ac34c9206395ddc611a7e8ed4d5c5a20e0c4be4'),
        ('mark_outbox_send_started', '098dec5ed40550b6bf674e9ba584988840ac4afa681c48cd25281f69631d8b7b'),
        ('set_outbox_kind_policy', '96ab2b4d3c9edfc20d3ba5a2837845a8efd37aa2eb5c306d0d4df7cf04f5c9a9'),
        ('record_outbox_fence', '3cbc8636386f6f16755ef3cab7f68a546ad85b35c6b0159a7510c32647ed0a0a')
    ) AS x(fn, want) LOOP
        SELECT count(*), min(encode(sha256(convert_to(p.prosrc, 'UTF8')), 'hex'))
          INTO v_cnt, v_got
          FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'bem_control' AND p.proname = r.fn;
        IF v_cnt <> 1 OR v_got IS DISTINCT FROM r.want THEN
            RAISE EXCEPTION 'FINAL_ZAVOD_FN_BODY_MISMATCH: % (функций %, отпечаток %)', r.fn, v_cnt, v_got;
        END IF;
    END LOOP;
END
$zavod_fp$;

-- Ни одной команды безопасности после этой строки быть не должно.
-- BEM954-FINAL-SECURITY-CHECKPOINT: 05_final_state_check.sql

