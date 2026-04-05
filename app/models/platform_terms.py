from typing import Literal


PlatformModule = Literal["EOR", "Payroll", "HRIS"]
SalesMotion = Literal["direct_client", "recruitment_partner"]
BundleLabel = Literal[
    "EOR only",
    "Payroll only",
    "HRIS only",
    "EOR + Payroll",
    "Payroll + HRIS",
    "EOR + HRIS",
    "Full Platform",
]
