-- Drop existing tables and types (in reverse dependency order)
DROP TABLE IF EXISTS public.score CASCADE;
DROP TABLE IF EXISTS public.rubric CASCADE;
DROP TABLE IF EXISTS public.generated_note CASCADE;
DROP TABLE IF EXISTS public.synthetic_case CASCADE;
DROP TABLE IF EXISTS public.real_world_case CASCADE;
DROP TABLE IF EXISTS public.case CASCADE;

-- Drop existing types
DROP TYPE IF EXISTS rubric_validation CASCADE;
DROP TYPE IF EXISTS synthetic_case_turn_buckets CASCADE;
DROP TYPE IF EXISTS synthetic_case_patient_style CASCADE;
DROP TYPE IF EXISTS synthetic_case_clinician_style CASCADE;
DROP TYPE IF EXISTS synthetic_case_pressure CASCADE;
DROP TYPE IF EXISTS synthetic_case_mood CASCADE;
DROP TYPE IF EXISTS case_status CASCADE;

-- Create types
CREATE TYPE case_status AS ENUM ('generation', 'review', 'evaluation');
CREATE TYPE synthetic_case_mood AS ENUM ('patient is frustrated', 'patient is tearful', 'patient is embarrassed',
        'patient is defensive', 'clinician is concerned', 'clinician is rushed', 'clinician is warm',
        'clinician is brief');
CREATE TYPE synthetic_case_pressure AS ENUM ('time pressure on the visit', 'insurance denied prior authorization',
        'formulary change', 'refill limit reached', 'patient traveling soon', 'side-effect report just came in');
CREATE TYPE synthetic_case_clinician_style AS ENUM ('warm and chatty', 'brief and efficient', 
        'cautious and inquisitive', 'over-explainer');
CREATE TYPE synthetic_case_patient_style AS ENUM ('anxious and talkative', 'confused and forgetful', 
        'assertive and informed', 'agreeable but vague');
CREATE TYPE synthetic_case_turn_buckets AS ENUM ('short', 'medium', 'long');
CREATE TYPE rubric_validation AS ENUM ('not_evaluated', 'refused', 'accepted');

-- Create tables
CREATE TABLE public.case
(
    id                serial PRIMARY KEY,
    created           timestamp   NOT NULL,
    updated           timestamp   NOT NULL,
    name              text        NOT NULL UNIQUE,
    transcript        JSON        NOT NULL,
    limited_chart     JSON        NOT NULL,
    profile           text        NOT NULL,
    validation_status case_status NOT NULL,
    batch_identifier  text        NOT NULL,
    tags              JSON        NOT NULL
);

CREATE TABLE public.real_world_case
(
    id                          serial PRIMARY KEY,
    created                     timestamp NOT NULL,
    updated                     timestamp NOT NULL,
    case_id                     serial    NOT NULL UNIQUE,
    customer_identifier         text      NOT NULL,
    patient_note_hash           text      NOT NULL,
    topical_exchange_identifier text      NOT NULL,
    publishable                 boolean   NOT NULL,
    start_time                  real      NOT NULL,
    end_time                    real      NOT NULL,
    duration                    real      NOT NULL,
    audio_llm_vendor            text      NOT NULL,
    audio_llm_name              text      NOT NULL,
    CONSTRAINT fk_real_world_case_case
        FOREIGN KEY (case_id)
            REFERENCES public.case (id)
            ON DELETE CASCADE
);

CREATE TABLE public.synthetic_case
(
    id                              serial PRIMARY KEY,
    created                         timestamp                      NOT NULL,
    updated                         timestamp                      NOT NULL,
    case_id                         serial                         NOT NULL UNIQUE,
    category                        text                           NOT NULL,
    turn_total                      int                            NOT NULL,
    speaker_sequence                JSON                          NOT NULL,
    clinician_to_patient_turn_ratio real                           NOT NULL,
    mood                            synthetic_case_mood            NOT NULL,
    pressure                        synthetic_case_pressure        NOT NULL,
    clinician_style                 synthetic_case_clinician_style NOT NULL,
    patient_style                   synthetic_case_patient_style   NOT NULL,
    turn_buckets                    synthetic_case_turn_buckets    NOT NULL,
    text_llm_vendor                 text                           NOT NULL,
    text_llm_name                   text                           NOT NULL,
    temperature                     real                           NOT NULL,
    CONSTRAINT fk_synthetic_case_case
        FOREIGN KEY (case_id)
            REFERENCES public.case (id)
            ON DELETE CASCADE
);

CREATE TABLE public.generated_note
(
    id                       serial PRIMARY KEY,
    created                  timestamp NOT NULL,
    updated                  timestamp NOT NULL,
    case_id                  serial    NOT NULL,
    cycle_duration           int       NOT NULL,
    cycle_count              int       NOT NULL,
    cycle_transcript_overlap int       NOT NULL,
    text_llm_vendor          text      NOT NULL,
    text_llm_name            text      NOT NULL,
    note_json                JSON      NOT NULL,
    hyperscribe_version      text      NOT NULL,
    staged_questionnaires    JSON      NOT NULL,
    transcript2instructions  JSON      NOT NULL,
    instruction2parameters   JSON      NOT NULL,
    parameters2command       JSON      NOT NULL,
    failed                   boolean   NOT NULL,
    errors                   JSON      NOT NULL,
    CONSTRAINT fk_generated_note_case
        FOREIGN KEY (case_id)
            REFERENCES public.case (id)
            ON DELETE CASCADE
);

CREATE TABLE public.rubric
(
    id                             serial PRIMARY KEY,
    created                        timestamp         NOT NULL,
    updated                        timestamp         NOT NULL,
    case_id                        serial            NOT NULL,
    parent_rubric_id               int REFERENCES rubric (id),
    validation_timestamp           timestamp NULL,
    validation                     rubric_validation NOT NULL,
    author                         text              NOT NULL,
    rubric                         JSON              NOT NULL,
    case_provenance_classification text              NOT NULL,
    comments                       text              NOT NULL,
    text_llm_vendor                text              NOT NULL,
    text_llm_name                  text              NOT NULL,
    temperature                    real              NOT NULL,
    CONSTRAINT fk_rubric_case
        FOREIGN KEY (case_id)
            REFERENCES public.case (id)
            ON DELETE CASCADE
);

CREATE TABLE public.score
(
    id                serial PRIMARY KEY,
    created           timestamp NOT NULL,
    updated           timestamp NOT NULL,
    rubric_id         serial    NOT NULL,
    generated_note_id serial    NOT NULL,
    scoring_result    JSON      NOT NULL,
    overall_score     real NULL,
    comments          text      NOT NULL,
    text_llm_vendor   text      NOT NULL,
    text_llm_name     text      NOT NULL,
    temperature       real      NOT NULL,
    CONSTRAINT fk_score_case
        FOREIGN KEY (rubric_id)
            REFERENCES public.rubric (id)
            ON DELETE CASCADE,
    CONSTRAINT fk_score_generated_note
        FOREIGN KEY (generated_note_id)
            REFERENCES public.generated_note (id)
            ON DELETE CASCADE
);

-- Create indexes
CREATE INDEX idx_case_name ON public.case (name);
CREATE INDEX idx_real_world_case_case_id ON public.real_world_case (case_id);
CREATE INDEX idx_real_world_case_customer_patient ON public.real_world_case (customer_identifier, patient_note_hash);
CREATE INDEX idx_synthetic_case_case_id ON public.synthetic_case (case_id);
CREATE INDEX idx_generated_note_case_id ON public.generated_note (case_id);
CREATE INDEX idx_generated_note_failed ON public.generated_note (failed);
CREATE INDEX idx_rubric_case_id ON public.rubric (case_id);
CREATE INDEX idx_score_case_id_generated_note_id ON public.score (rubric_id, generated_note_id);