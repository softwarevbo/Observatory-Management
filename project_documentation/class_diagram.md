classDiagram
    class User {
        +int userId
        +string username
        +string email
        +string passwordHash
        +string role
        +bool isActive
        +datetime lastLogin
        +login()
        +logout()
        +resetPassword()
    }

    class Role {
        +int roleId
        +string roleName
        +string description
        +List~Permission~ permissions
        +assignPermission()
        +removePermission()
    }

    class AuditUniverse {
        +int universeId
        +string entityName
        +string category
        +string riskLevel
        +string owner
        +datetime lastAuditDate
        +addAuditableEntity()
        +updateRiskRating()
        +getAuditHistory()
    }

    class AuditPlan {
        +int planId
        +string planName
        +int fiscalYear
        +date startDate
        +date endDate
        +string status
        +string approvedBy
        +createPlan()
        +approvePlan()
        +revisePlan()
    }

    class AuditEngagement {
        +int engagementId
        +string title
        +string objective
        +string scope
        +date plannedStart
        +date plannedEnd
        +date actualStart
        +date actualEnd
        +string status
        +string phase
        +createEngagement()
        +updateStatus()
        +closeEngagement()
    }

    class AuditTeam {
        +int teamId
        +int engagementId
        +int leadAuditorId
        +List~int~ memberIds
        +assignMember()
        +removeMember()
        +getTeamDetails()
    }

    class WorkProgram {
        +int programId
        +int engagementId
        +string procedureName
        +string objective
        +string testSteps
        +string status
        +string performedBy
        +datetime performedDate
        +executeStep()
        +markComplete()
        +addEvidence()
    }

    class Finding {
        +int findingId
        +int engagementId
        +string title
        +string description
        +string riskRating
        +string rootCause
        +string impact
        +string criteria
        +string condition
        +string recommendation
        +string managementResponse
        +string status
        +logFinding()
        +escalateFinding()
        +closeFinding()
    }

    class Recommendation {
        +int recommendationId
        +int findingId
        +string description
        +string priority
        +date dueDate
        +string assignedTo
        +string status
        +int completionPercent
        +assignOwner()
        +updateProgress()
        +markImplemented()
    }

    class ActionPlan {
        +int actionId
        +int recommendationId
        +string actionDescription
        +date targetDate
        +string owner
        +string evidence
        +string verificationStatus
        +string closedBy
        +datetime closedDate
        +submitAction()
        +verifyAction()
        +reopenAction()
    }

    class AuditReport {
        +int reportId
        +int engagementId
        +string reportType
        +string executiveSummary
        +string overallRating
        +string preparedBy
        +string reviewedBy
        +datetime issuedDate
        +string status
        +draftReport()
        +reviewReport()
        +issueReport()
        +distributeReport()
    }

    class RiskAssessment {
        +int assessmentId
        +int universeId
        +int assessmentYear
        +float inherentRisk
        +float controlEffectiveness
        +float residualRisk
        +string riskCategory
        +assessRisk()
        +updateRisk()
        +generateHeatMap()
    }

    class Notification {
        +int notifId
        +int userId
        +string type
        +string message
        +bool isRead
        +datetime createdAt
        +sendNotification()
        +markRead()
    }

    User "1" --> "1" Role : has
    AuditPlan "1" --> "many" AuditEngagement : contains
    AuditEngagement "1" --> "1" AuditTeam : assigned to
    AuditEngagement "1" --> "many" WorkProgram : includes
    AuditEngagement "1" --> "many" Finding : produces
    AuditEngagement "1" --> "1" AuditReport : generates
    Finding "1" --> "many" Recommendation : leads to
    Recommendation "1" --> "many" ActionPlan : tracked by
    AuditUniverse "1" --> "many" RiskAssessment : evaluated by
    AuditUniverse "1" --> "many" AuditEngagement : subject of
    User "1" --> "many" Notification : receives
    User "many" --> "many" AuditTeam : member of