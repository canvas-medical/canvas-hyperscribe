# Canvas Hyperscribe Plugin Specification

## Overview

**Name:** hyperscribe
**Version:** 2026-01-12 v0.2.155 (main)
**SDK Version:** 0.85.0
**Description:** A Canvas plugin that creates structured clinical commands from audio recordings of patient-provider encounters.

Hyperscribe is an AI-powered ambient scribe that listens to medical conversations between patients and healthcare providers, transcribes the audio, and automatically generates structured clinical documentation commands in the Canvas Medical platform.

## Core Functionality

### What It Does

1. **Audio Capture & Transcription**: Records patient-provider conversations in real-time, processing audio in configurable intervals (default 20 seconds)
2. **Speaker Identification**: Uses LLM to distinguish between speakers (patient, clinician, nurse, parent, etc.)
3. **Clinical Instruction Detection**: Analyzes transcripts to identify clinical actions and documentation needs
4. **Command Generation**: Automatically creates structured Canvas commands (prescriptions, diagnoses, lab orders, etc.)
5. **Real-time Progress Updates**: Sends WebSocket updates to the UI showing transcription and processing status

## Architecture

### Handler Components

| Handler | Description | Location |
|---------|-------------|----------|
| `CaptureButton` | Action button in note header to launch Hyperscribe | `handlers/capture_button.py` |
| `CaptureView` | Main API serving the UI and processing audio/transcript | `handlers/capture_view.py` |
| `ReviewerButton` | Button to view LLM decision audit trail | `handlers/reviewer_button.py` |
| `ReviewerDisplay` | Displays the audit page | `handlers/reviewer_display.py` |
| `TranscriptButton` | Button to view transcript | `handlers/transcript_button.py` |
| `TranscriptDisplay` | Displays the transcript page | `handlers/transcript_display.py` |
| `ProgressDisplay` | WebSocket handler for real-time progress messages | `handlers/progress_display.py` |
| `WebSocketDealer` | Provides WebSocket capability | `handlers/web_socket_dealer.py` |
| `CaseBuilder` | Creates commands from Case Builder (testing/evaluation) | `handlers/case_builder.py` |
| `TuningLauncher` | Button for tuning mode recording | `handlers/tuning_launcher.py` |
| `TuningArchiver` | Stores audio/chart data in S3 for tuning | `handlers/tuning_archiver.py` |
| `CustomizationApp` | Application for user customization | `handlers/customization_app.py` |
| `CustomizationDisplay` | Displays customization UI | `handlers/customization_display.py` |

### Processing Pipeline

```
Audio/Text Input
       |
       v
+------------------+
|  CaptureView     |  <-- Receives audio chunks via POST /audio/<patient>/<note>
+------------------+       or text via POST /transcript/<patient>/<note>
       |
       v
+------------------+
|  CycleData       |  <-- Stores chunks in AWS S3
+------------------+
       |
       v
+------------------+
|   Commander      |  <-- Main processing orchestrator
+------------------+
       |
       v
+------------------+
| AudioInterpreter |  <-- Transcription & speaker detection
+------------------+
       |
       v
+------------------+
| detect_instructions() |  <-- LLM identifies clinical actions
+------------------+
       |
       v
+------------------+
| Command Classes  |  <-- 33 supported command types
+------------------+
       |
       v
+------------------+
| Canvas SDK Effects | <-- originate() or edit() commands
+------------------+
```

### Key Libraries

| Library | Purpose |
|---------|---------|
| `Commander` | Main orchestrator - converts audio to Canvas commands |
| `AudioInterpreter` | Handles transcription and instruction detection |
| `LimitedCache` | Caches patient/provider data for LLM context |
| `ImplementedCommands` | Registry of all 33 supported command types |
| `AwsS3` | AWS S3 client for storing logs, audits, and audio |
| `StopAndGo` | Session state management (pause/resume/end) |
| `MemoryLog` | Logging throughout processing pipeline |
| `LlmTurnsStore` | Stores LLM conversation turns for auditing |

## Supported Commands (33 Total)

### Clinical Documentation
- `HistoryOfPresentIllness` - HPI narrative
- `ReasonForVisit` - Chief complaint
- `PhysicalExam` - Physical exam findings
- `ReviewOfSystem` - ROS documentation
- `StructuredAssessment` - Structured assessment

### Diagnoses & Conditions
- `Diagnose` - Add new diagnosis
- `UpdateDiagnose` - Update existing diagnosis
- `Assess` - Assessment for existing condition
- `ResolveCondition` - Mark condition as resolved

### Medications & Prescriptions
- `Prescription` - New prescription
- `Refill` - Medication refill
- `AdjustPrescription` - Adjust existing prescription
- `Medication` - Medication statement
- `StopMedication` - Discontinue medication

### Orders
- `LabOrder` - Laboratory order
- `ImagingOrder` - Imaging/radiology order
- `Refer` - Referral order
- `Immunize` - Immunization administration
- `ImmunizationStatement` - Immunization history

### History
- `MedicalHistory` - Past medical history
- `FamilyHistory` - Family medical history
- `SurgeryHistory` - Surgical history
- `Allergy` - Add allergy
- `RemoveAllergy` - Remove allergy

### Care Planning
- `Goal` - Patient goal
- `UpdateGoal` - Update existing goal
- `CloseGoal` - Close/complete goal
- `Plan` - Plan narrative
- `FollowUp` - Follow-up scheduling
- `Instruct` - Patient instructions
- `Task` - Staff task creation

### Procedures & Vitals
- `Perform` - Procedure performed
- `Vitals` - Vital signs
- `Questionnaire` - Questionnaire completion

## LLM Integration

### Supported LLM Vendors

| Vendor | Audio Support | Text Support | Models |
|--------|--------------|--------------|--------|
| OpenAI | Yes | Yes | `gpt-4o-audio-preview`, `gpt-4.1`, `o3` |
| Google | Yes | Yes | `gemini-2.5-flash`, `gemini-2.5-pro` |
| Anthropic | No | Yes | `claude-sonnet-4-5-20250929`, `claude-opus-4-1-20250805` |
| ElevenLabs | Yes | No | `scribe_v1` |

### LLM Processing Flow

1. **Audio to Text** (AudioLLM vendor)
   - Transcribes audio with speaker detection
   - Uses previous transcript context for continuity

2. **Instruction Detection** (TextLLM vendor)
   - Flat detection for < 5 staged commands
   - Hierarchical (section-based) detection for >= 5 staged commands
   - Sections: Assessment, History, Objective, Plan, Procedures, Subjective

3. **Parameter Extraction** (TextLLM vendor)
   - Converts instructions to structured command parameters
   - Validates against JSON schemas

4. **Command Generation** (Canvas SDK)
   - Creates Canvas SDK command objects
   - Generates clinical shorthand summaries

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/capture/<patient>/<note>/<reference>` | GET | Launch Hyperscribe UI |
| `/capture/new-session/<patient>/<note>` | POST | Start new recording session |
| `/capture/idle/<patient>/<note>/<action>` | POST | Pause/resume/end session |
| `/audio/<patient>/<note>` | POST | Submit audio chunk |
| `/transcript/<patient>/<note>` | POST | Submit text transcript |
| `/draft/<patient>/<note>` | GET/POST | Draft transcript storage |
| `/capture/render/<patient>/<note>/<user>` | POST | Trigger command rendering |
| `/feedback/<patient>/<note>` | POST | Submit user feedback |
| `/progress` | GET | Progress WebSocket endpoint |

## Configuration (Secrets)

### Core Settings
| Secret | Description | Default |
|--------|-------------|---------|
| `APISigningKey` | API authentication key | Required |
| `AudioIntervalSeconds` | Duration of each audio chunk | 20 |
| `MaxWorkers` | Concurrent command processing threads | 3 |

### LLM Configuration
| Secret | Description |
|--------|-------------|
| `VendorAudioLLM` | Audio transcription vendor (OpenAI/Google) |
| `KeyAudioLLM` | Audio LLM API key |
| `VendorTextLLM` | Text LLM vendor (OpenAI/Google/Anthropic) |
| `KeyTextLLM` | Text LLM API key |

### Access Control
| Secret | Description |
|--------|-------------|
| `StaffersList` | Allowed/excluded staff IDs |
| `StaffersPolicy` | Allow (y) or exclude (n) listed staffers |
| `TrialStaffersList` | Trial users (test patients only) |
| `CommandsList` | Allowed/excluded command types |
| `CommandsPolicy` | Allow (y) or exclude (n) listed commands |

### Storage & Logging
| Secret | Description |
|--------|-------------|
| `AwsBucketLogs` | S3 bucket for logs |
| `AwsBucketTuning` | S3 bucket for tuning data |
| `AwsKey`, `AwsSecret`, `AwsRegion` | AWS credentials |
| `AuditLLMDecisions` | Enable LLM decision auditing |

### Advanced Settings
| Secret | Description | Default |
|--------|-------------|---------|
| `CycleTranscriptOverlap` | Words from previous chunk for context | 100 |
| `HierarchicalDetectionThreshold` | Commands threshold for hierarchical mode | 5 |
| `StructuredReasonForVisit` | Use structured RFV | No |
| `IsTuning` | Enable tuning mode (hides main UI) | No |

## Data Flow & Storage

### S3 Storage Structure
```
hyperscribe-{canvas_instance}/
├── audits/              # LLM decision audit files
├── finals/              # Concatenated cycle logs
│   └── {date}/
│       └── {patient}-{note}/
│           └── {cycle}.log
├── llm_turns/           # Individual LLM conversation logs
├── partials/            # Step-by-step processing logs
├── feedback/            # User feedback submissions
│   └── {note}/
│       └── {timestamp}
└── tuning/              # Tuning mode recordings
```

### Session State Management

The `StopAndGo` class manages session state:
- **Running**: Commander is actively processing
- **Paused**: Recording paused, preserves state
- **Ended**: Session complete, triggers final audit
- **Waiting Cycles**: Queue of audio chunks pending processing

## UI Components

### Templates
- `hyperscribe.html` - Main capture interface
- `reviewer.html` - LLM decision audit viewer
- `transcript.html` - Transcript display
- `customization.html` - User customization settings
- `capture_tuning_case.html` - Tuning mode interface

### WebSocket Communication
Real-time progress updates via WebSocket at:
```
wss://{host}/plugin-io/ws/hyperscribe/progresses_{note_id}/
```

Message sections:
- `events:1` - New medical instructions
- `events:2` - Updated medical instructions
- `events:4` - Technical progress
- `events:7` - Session events (start/pause/resume/stop)
- `transcript` - Live transcript updates

## Security & Authentication

1. **API Signing**: All API endpoints use HMAC-based URL signing with expiration
2. **Staff Access Control**: Configurable allow/deny lists for staff access
3. **Patient Filtering**: Trial users limited to test patients (`Hyperscribe* ZZTest*`)
4. **Note Editability**: Button only visible for editable notes

## Error Handling

- **Audio Processing**: Continues even if transcription fails for a cycle
- **LLM Retries**: 3 attempts for HTTP errors, 3 attempts for JSON parsing
- **Validation**: JSON Schema validation for all LLM responses
- **Feedback**: User feedback stored in S3 and Notion for issue tracking

## Evaluation Framework

Located in `/evaluations/`:
- Test case builders for various scenarios
- End-to-end evaluation testing
- Synthetic case generation
- PostgreSQL-based auditing
- Statistical analysis tools

## Dependencies

```toml
[project]
requires-python = ">=3.11,<3.13"
dependencies = [
    "canvas>=0.58.1",
    "canvas[test-utils]>=0.58.1",
    "ffmpeg-python>=0.2.0",
]
```

## Installation & Deployment

```bash
# Install plugin
canvas install --host my-canvas-host hyperscribe

# Set secrets
canvas config set hyperscribe --host my-canvas-host KeyTextLLM=xxx KeyAudioLLM=xxx ...

# View logs
canvas logs --host my-canvas-host

# Disable plugin
canvas disable --host my-canvas-host hyperscribe

# Uninstall plugin
canvas uninstall --host my-canvas-host hyperscribe
```

## Key Implementation Details

### Command Base Class Pattern
All 33 commands inherit from `Base` class (`commands/base.py`) which provides:
- `class_name()` - Command identifier
- `schema_key()` - Canvas SDK schema key
- `note_section()` - SOAP note section association
- `command_parameters()` - Parameter structure for LLM
- `command_from_json()` - Convert LLM output to Canvas command
- `staged_command_extract()` - Extract data from existing commands

### Questionnaire Commands
Special handling for questionnaire-type commands (`PhysicalExam`, `Questionnaire`, `ReviewOfSystem`, `StructuredAssessment`) via `BaseQuestionnaire` class - these update in place rather than creating new instances.

### Hierarchical vs Flat Detection
- **Flat Detection**: Used when < 5 staged commands; processes entire transcript at once
- **Hierarchical Detection**: Used when >= 5 staged commands; splits transcript by SOAP sections for more accurate processing

### Custom Prompts
Users can configure custom prompts per command type via `CustomPrompts` setting, allowing organization-specific formatting rules.
