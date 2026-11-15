export interface paths {
    "/auth/register": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Register */
        post: operations["register_auth_register_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Login */
        post: operations["login_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Me */
        get: operations["me_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/personas": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Personas
         * @description Public: personas a new user can choose at onboarding (synthetic freelancer profiles).
         */
        get: operations["personas_auth_personas_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/jobs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Inbox
         * @description Job inbox: new jobs, ranked by fit where a run has already analysed them.
         */
        get: operations["inbox_jobs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/jobs/{job_id}/runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Analyse Job */
        post: operations["analyse_job_jobs__job_id__runs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Runs */
        get: operations["list_runs_runs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/runs/dead-letters": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Dead Letters */
        get: operations["dead_letters_runs_dead_letters_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/runs/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Run Detail */
        get: operations["run_detail_runs__run_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/runs/{run_id}/history": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Checkpoint History */
        get: operations["checkpoint_history_runs__run_id__history_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/runs/{run_id}/replay": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Replay */
        post: operations["replay_runs__run_id__replay_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/runs/{run_id}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Run Events
         * @description Server-Sent Events: node-by-node progress; the stream ends at an approval gate or when the run is done.
         */
        get: operations["run_events_runs__run_id__events_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/runs/{run_id}/retry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Retry */
        post: operations["retry_runs__run_id__retry_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/runs/{run_id}/regenerate-paragraph": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Regenerate Paragraph */
        post: operations["regenerate_paragraph_runs__run_id__regenerate_paragraph_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/approvals/pending": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Pending
         * @description What a page refresh calls. Read from the checkpoint, so it survives refreshes and API restarts.
         */
        get: operations["pending_approvals_pending_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/runs/{run_id}/approval": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Decide */
        post: operations["decide_runs__run_id__approval_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/conversations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Threads */
        get: operations["threads_conversations_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/conversations/{thread_id}/runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Handle Thread */
        post: operations["handle_thread_conversations__thread_id__runs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/pipeline": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Pipeline */
        get: operations["pipeline_pipeline_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/runs/{run_id}/outcome": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Outcome
         * @description Marketplace event (viewed/replied/...): moves the card and feeds outcome memory through its promotion rule.
         */
        post: operations["outcome_runs__run_id__outcome_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/analytics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Analytics */
        get: operations["analytics_analytics_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/memory": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Memory */
        get: operations["memory_memory_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/memory/style/{rule_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Forget Style */
        delete: operations["forget_style_memory_style__rule_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/memory/outcome/{category}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Forget Outcome */
        delete: operations["forget_outcome_memory_outcome__category__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/settings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Settings */
        get: operations["get_settings_settings_get"];
        /** Put Settings */
        put: operations["put_settings_settings_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/settings/searches/{query}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Add Search */
        post: operations["add_search_settings_searches__query__post"];
        /** Remove Search */
        delete: operations["remove_search_settings_searches__query__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/connections/upwork": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Status */
        get: operations["status_connections_upwork_get"];
        put?: never;
        post?: never;
        /** Disconnect */
        delete: operations["disconnect_connections_upwork_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/connections/upwork/authorize": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Authorize */
        post: operations["authorize_connections_upwork_authorize_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/connections/upwork/callback": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Callback */
        get: operations["callback_connections_upwork_callback_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/connections/upwork/catalog": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Catalog */
        get: operations["catalog_connections_upwork_catalog_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/connections/upwork/mapping": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Mapping */
        put: operations["mapping_connections_upwork_mapping_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/connections/upwork/mode": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Mode */
        put: operations["mode_connections_upwork_mode_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/runs/{run_id}/platform-confirmation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Confirm */
        post: operations["confirm_runs__run_id__platform_confirmation_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/connections/github": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Status */
        get: operations["status_connections_github_get"];
        put?: never;
        post?: never;
        /** Disconnect */
        delete: operations["disconnect_connections_github_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/connections/github/authorize": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Authorize */
        post: operations["authorize_connections_github_authorize_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/connections/github/imports": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Imports */
        get: operations["imports_connections_github_imports_get"];
        put?: never;
        /** Import Readme */
        post: operations["import_readme_connections_github_imports_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/portfolio/documents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Documents */
        get: operations["documents_portfolio_documents_get"];
        put?: never;
        /** Upload */
        post: operations["upload_portfolio_documents_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/portfolio/github": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Repository */
        post: operations["repository_portfolio_github_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/portfolio/documents/{document_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Delete */
        delete: operations["delete_portfolio_documents__document_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/portfolio/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Search */
        get: operations["search_portfolio_search_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/upwork-connected": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Upwork Connected */
        get: operations["upwork_connected_upwork_connected_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/upwork-connection-failed": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Upwork Failed */
        get: operations["upwork_failed_upwork_connection_failed_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/admin/retry-degraded": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Retry Degraded */
        post: operations["retry_degraded_admin_retry_degraded_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** AnalyticsOut */
        AnalyticsOut: {
            /** Runs */
            runs: number;
            /** By Status */
            by_status: {
                [key: string]: number;
            };
            /** Connects Spent */
            connects_spent: number;
            /** Latency Ms P50 */
            latency_ms_p50: number | null;
            /** Latency Ms P95 */
            latency_ms_p95: number | null;
            /** Jobs Analyzed */
            jobs_analyzed: number;
            /** Proposals */
            proposals: number;
            /** Average Tokens Per Job */
            average_tokens_per_job: number | null;
            /** Average Tokens Per Proposal */
            average_tokens_per_proposal: number | null;
            /** Average Output Tokens Per Second */
            average_output_tokens_per_second: number | null;
            /** Average Cost Per Proposal Usd */
            average_cost_per_proposal_usd: number | null;
            /** Priced Proposals */
            priced_proposals: number;
            /** Unpriced Proposals */
            unpriced_proposals: number;
            /** Billing */
            billing: string;
            /** Hardware Note */
            hardware_note: string | null;
            /** Run Metrics */
            run_metrics: components["schemas"]["RunMetricOut"][];
            /** Top Skip Reasons */
            top_skip_reasons: [
                string,
                number
            ][];
            /** Top Rejection Reasons */
            top_rejection_reasons: [
                string,
                number
            ][];
            /** Reply Rate By Category */
            reply_rate_by_category: {
                [key: string]: {
                    [key: string]: unknown;
                };
            };
        };
        /**
         * ApprovalDecision
         * @description What the web UI sends back to resume the interrupted thread.
         */
        ApprovalDecision: {
            /**
             * Action
             * @enum {string}
             */
            action: "approve" | "edit" | "reject";
            /** Edited Cover Letter */
            edited_cover_letter?: string | null;
            /** Reason */
            reason?: string | null;
        };
        /** AuthorizationOut */
        AuthorizationOut: {
            /** Authorization Url */
            authorization_url: string | null;
            /** Status */
            status: string;
        };
        /** ConnectionStatus */
        ConnectionStatus: {
            /** Connected */
            connected: boolean;
            /** Mode */
            mode: string;
            /** Status */
            status: string;
            /** Mapped Operations */
            mapped_operations: string[];
            /** Required Operations */
            required_operations: string[];
            /** Ready */
            ready: boolean;
            /**
             * Reads Ready
             * @default false
             */
            reads_ready: boolean;
        };
        /** DocumentMetadata */
        DocumentMetadata: {
            /** Title */
            title: string;
            /** Project */
            project: string;
            /** Skills */
            skills?: string[];
            /** Date */
            date?: string | null;
            /** Client Industry */
            client_industry?: string | null;
            /** Outcome */
            outcome?: string | null;
            /**
             * Provenance
             * @default user-upload
             */
            provenance: string;
            /**
             * Authorship Confirmed
             * @default false
             */
            authorship_confirmed: boolean;
        };
        /** GitHubImportsOut */
        GitHubImportsOut: {
            /**
             * Items
             * @default []
             */
            items: {
                [key: string]: unknown;
            }[];
        };
        /** GitHubStatus */
        GitHubStatus: {
            /** Connected */
            connected: boolean;
            /** Status */
            status: string;
            /** Authorization Url */
            authorization_url?: string | null;
            /** Authorization Message */
            authorization_message?: string | null;
            /** Login */
            login?: string | null;
            /**
             * Read Only
             * @default true
             */
            read_only: boolean;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** HealthOut */
        HealthOut: {
            /**
             * Api
             * @default ok
             */
            api: string;
            /**
             * Marketplace
             * @enum {string}
             */
            marketplace: "ok" | "degraded";
            /** Queued Degraded Runs */
            queued_degraded_runs: number;
        };
        /** ImportReadme */
        ImportReadme: {
            /** Owner */
            owner: string;
            /** Repo */
            repo: string;
            /**
             * Path
             * @default README.md
             */
            path: string;
            /** Ref */
            ref?: string | null;
            /**
             * Authorship Confirmed
             * @default false
             */
            authorship_confirmed: boolean;
        };
        /** JobCard */
        JobCard: {
            /** Job Id */
            job_id: string;
            /** Title */
            title: string;
            /**
             * Description
             * @default
             */
            description: string;
            /**
             * Client Id
             * @default
             */
            client_id: string;
            /** Connects Cost */
            connects_cost?: number | null;
            /** Budget Max */
            budget_max?: number | null;
            /**
             * Required Skills
             * @default []
             */
            required_skills: string[];
            latest_run?: components["schemas"]["RunOut"] | null;
            /** Fit Score */
            fit_score?: number | null;
            /** Risk Score */
            risk_score?: number | null;
            /** Recommended Action */
            recommended_action?: string | null;
            /** Price */
            price?: number | null;
        };
        /** LoginIn */
        LoginIn: {
            /** Email */
            email: string;
            /** Password */
            password: string;
        };
        /** MappingIn */
        MappingIn: {
            /** Catalog Sha256 */
            catalog_sha256: string;
            /** Operations */
            operations: {
                [key: string]: unknown;
            };
        };
        /** MemoryOut */
        MemoryOut: {
            /** Style */
            style: {
                [key: string]: unknown;
            }[];
            /** Outcome */
            outcome: {
                [key: string]: {
                    [key: string]: unknown;
                };
            };
        };
        /** ModeIn */
        ModeIn: {
            /** Mode */
            mode: string;
        };
        /** OutcomeIn */
        OutcomeIn: {
            /**
             * Outcome
             * @enum {string}
             */
            outcome: "viewed" | "replied" | "interview" | "hired" | "lost";
        };
        /** ParagraphRegenerationIn */
        ParagraphRegenerationIn: {
            /** Claim Index */
            claim_index: number;
        };
        /** ParagraphRegenerationOut */
        ParagraphRegenerationOut: {
            /** Text */
            text: string;
        };
        /** PipelineOut */
        PipelineOut: {
            /** Columns */
            columns: {
                [key: string]: components["schemas"]["RunOut"][];
            };
        };
        /** PlatformConfirmationIn */
        PlatformConfirmationIn: {
            /** Review Hash */
            review_hash: string;
            /** Confirm On Upwork */
            confirm_on_upwork: boolean;
            /** Attachments Choice */
            attachments_choice?: string | null;
        };
        /** RegisterIn */
        RegisterIn: {
            /** Email */
            email: string;
            /** Password */
            password: string;
            /**
             * Freelancer Id
             * @default sample-ai-engineer
             */
            freelancer_id: string;
        };
        /** ReplayIn */
        ReplayIn: {
            /** Checkpoint Id */
            checkpoint_id: string;
            /** Node */
            node: string;
        };
        /** RepositoryIn */
        RepositoryIn: {
            /** Owner */
            owner: string;
            /** Repo */
            repo: string;
            /** Path */
            path: string;
            /** Ref */
            ref?: string | null;
            /** Kind */
            kind: string;
            metadata: components["schemas"]["DocumentMetadata"];
        };
        /** RunDetail */
        RunDetail: {
            /** Run Id */
            run_id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "bid" | "conv";
            /** Target */
            target: string;
            /** Status */
            status: string;
            /** Trace Id */
            trace_id: string;
            /**
             * Degraded
             * @default false
             */
            degraded: boolean;
            /** Created At */
            created_at: number;
            /** Outcome */
            outcome?: string | null;
            /** Pending */
            pending?: {
                [key: string]: unknown;
            } | null;
            /**
             * Summary
             * @default {}
             */
            summary: {
                [key: string]: unknown;
            };
        };
        /** RunMetricOut */
        RunMetricOut: {
            /** Run Id */
            run_id: string;
            /** Target */
            target: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "bid" | "conv";
            /** Status */
            status: string;
            /** Trace Id */
            trace_id: string;
            /** Tokens Used */
            tokens_used: number;
            /** Input Tokens */
            input_tokens: number;
            /** Output Tokens */
            output_tokens: number;
            /** Output Tokens Per Second */
            output_tokens_per_second: number | null;
            /** Latency Ms */
            latency_ms: number | null;
            /** Cost Usd */
            cost_usd: number | null;
            /** Usage Exact */
            usage_exact: boolean;
            /** Models */
            models: string[];
            /** Job Analyzed */
            job_analyzed: boolean;
            /** Proposal */
            proposal: boolean;
        };
        /** RunOut */
        RunOut: {
            /** Run Id */
            run_id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "bid" | "conv";
            /** Target */
            target: string;
            /** Status */
            status: string;
            /** Trace Id */
            trace_id: string;
            /**
             * Degraded
             * @default false
             */
            degraded: boolean;
            /** Created At */
            created_at: number;
            /** Outcome */
            outcome?: string | null;
        };
        /** SettingsIn */
        SettingsIn: {
            /** Hourly Rate Usd */
            hourly_rate_usd?: number | null;
            /** Minimum Project Budget Usd */
            minimum_project_budget_usd?: number | null;
            /** Weekly Connects Budget */
            weekly_connects_budget?: number | null;
            /** Auto Skip Low Fit */
            auto_skip_low_fit?: boolean | null;
        };
        /** SettingsOut */
        SettingsOut: {
            /** Hourly Rate Usd */
            hourly_rate_usd?: number | null;
            /** Minimum Project Budget Usd */
            minimum_project_budget_usd?: number | null;
            /** Weekly Connects Budget */
            weekly_connects_budget?: number | null;
            /** Auto Skip Low Fit */
            auto_skip_low_fit?: boolean | null;
            /**
             * Saved Searches
             * @default []
             */
            saved_searches: string[];
            /**
             * Autonomy Note
             * @default GigBid never sends a proposal or message without your approval.
             */
            autonomy_note: string;
        };
        /** ThreadCard */
        ThreadCard: {
            /** Thread Id */
            thread_id: string;
            /** Job Id */
            job_id: string;
            /** Client Id */
            client_id: string;
            /**
             * Last Message
             * @default
             */
            last_message: string;
            latest_run?: components["schemas"]["RunOut"] | null;
        };
        /** TokenOut */
        TokenOut: {
            /** Token */
            token: string;
            user: components["schemas"]["UserOut"];
        };
        /** UploadIn */
        UploadIn: {
            /** Filename */
            filename: string;
            /** Kind */
            kind: string;
            /** Content Base64 */
            content_base64: string;
            metadata: components["schemas"]["DocumentMetadata"];
        };
        /** UserOut */
        UserOut: {
            /** User Id */
            user_id: string;
            /** Email */
            email: string;
            /** Freelancer Id */
            freelancer_id: string;
            /**
             * Display Name
             * @default
             */
            display_name: string;
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    register_auth_register_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RegisterIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    login_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    me_auth_me_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    personas_auth_personas_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    inbox_jobs_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobCard"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    analyse_job_jobs__job_id__runs_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path: {
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_runs_runs_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    dead_letters_runs_dead_letters_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    run_detail_runs__run_id__get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    checkpoint_history_runs__run_id__history_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    replay_runs__run_id__replay_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReplayIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    run_events_runs__run_id__events_get: {
        parameters: {
            query?: {
                after?: number;
            };
            header?: {
                authorization?: string;
            };
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    retry_runs__run_id__retry_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    regenerate_paragraph_runs__run_id__regenerate_paragraph_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ParagraphRegenerationIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ParagraphRegenerationOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    pending_approvals_pending_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    decide_runs__run_id__approval_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ApprovalDecision"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    threads_conversations_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ThreadCard"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    handle_thread_conversations__thread_id__runs_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path: {
                thread_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    pipeline_pipeline_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PipelineOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    outcome_runs__run_id__outcome_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OutcomeIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    analytics_analytics_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    memory_memory_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MemoryOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    forget_style_memory_style__rule_id__delete: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path: {
                rule_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    forget_outcome_memory_outcome__category__delete: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path: {
                category: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_settings_settings_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SettingsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    put_settings_settings_put: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SettingsIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SettingsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    add_search_settings_searches__query__post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path: {
                query: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SettingsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    remove_search_settings_searches__query__delete: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path: {
                query: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SettingsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    status_connections_upwork_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectionStatus"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    disconnect_connections_upwork_delete: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    authorize_connections_upwork_authorize_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuthorizationOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    callback_connections_upwork_callback_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    catalog_connections_upwork_catalog_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    mapping_connections_upwork_mapping_put: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MappingIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    mode_connections_upwork_mode_put: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ModeIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    confirm_runs__run_id__platform_confirmation_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PlatformConfirmationIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    status_connections_github_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GitHubStatus"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    disconnect_connections_github_delete: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    authorize_connections_github_authorize_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GitHubStatus"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    imports_connections_github_imports_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GitHubImportsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    import_readme_connections_github_imports_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ImportReadme"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    documents_portfolio_documents_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upload_portfolio_documents_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UploadIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    repository_portfolio_github_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RepositoryIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_portfolio_documents__document_id__delete: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    search_portfolio_search_get: {
        parameters: {
            query?: {
                query?: string;
                kind?: string | null;
            };
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upwork_connected_upwork_connected_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    upwork_failed_upwork_connection_failed_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    health_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthOut"];
                };
            };
        };
    };
    retry_degraded_admin_retry_degraded_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
