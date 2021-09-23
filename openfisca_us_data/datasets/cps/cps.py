from openfisca_us_data.utils import US, dataset
from openfisca_us_data.datasets.cps.raw_cps import RawCPS
from pandas import DataFrame, Series
import h5py


@dataset
class CPS:
    name = "cps"
    model = US

    def generate(year: int) -> None:
        """Generates the CPS dataset.

        Args:
            year (int): The year of the raw CPS to use.
        """

        # Prepare raw CPS tables
        year = int(year)
        if year not in RawCPS.years:
            RawCPS.generate(year)

        raw_data = RawCPS.load(year)
        cps = h5py.File(CPS.file(year), mode="w")

        person, tax_unit, family, spm_unit, household = [
            raw_data[entity]
            for entity in (
                "person",
                "tax_unit",
                "family",
                "spm_unit",
                "household",
            )
        ]

        add_ID_variables(cps, person, tax_unit, family, spm_unit, household)
        add_personal_income_variables(cps, person)
        add_SPM_variables(cps, spm_unit)

        raw_data.close()
        cps.close()


def add_ID_variables(
    cps: h5py.File,
    person: DataFrame,
    tax_unit: DataFrame,
    family: DataFrame,
    spm_unit: DataFrame,
    household: DataFrame,
):
    """Add basic ID and weight variables.

    Args:
        cps (h5py.File): The CPS dataset file.
        person (DataFrame): The person table of the ASEC.
        tax_unit (DataFrame): The tax unit table created from the person table
            of the ASEC.
        family (DataFrame): The family table of the ASEC.
        spm_unit (DataFrame): The SPM unit table created from the person table
            of the ASEC.
        household (DataFrame): The household table of the ASEC.
    """
    # Add primary and foreign keys
    cps["person_id"] = person.PH_SEQ * 100 + person.P_SEQ
    cps["family_id"] = family.FH_SEQ * 10 + family.FFPOS
    cps["household_id"] = household.H_SEQ
    cps["person_tax_unit_id"] = person.TAX_ID
    cps["person_spm_unit_id"] = person.SPM_ID
    cps["tax_unit_id"] = tax_unit.TAX_ID
    cps["spm_unit_id"] = spm_unit.SPM_ID
    cps["person_household_id"] = person.PH_SEQ
    cps["person_family_id"] = person.PH_SEQ * 10 + person.PF_SEQ

    # Add weights
    cps["person_weight"] = person.A_FNLWGT / 1e2
    cps["family_weight"] = family.FSUP_WGT / 1e2

    # Tax unit weight is the weight of the containing family.
    family_weight = Series(
        cps["family_weight"][...], index=cps["family_id"][...]
    )
    person_family_id = cps["person_family_id"][...]
    persons_family_weight = Series(family_weight[person_family_id])
    cps["tax_unit_weight"] = persons_family_weight.groupby(
        cps["person_tax_unit_id"][...]
    ).first()

    cps["spm_unit_weight"] = spm_unit.SPM_WEIGHT / 1e2

    cps["household_weight"] = household.HSUP_WGT / 1e2


def add_personal_income_variables(cps: h5py.File, person: DataFrame):
    """Add income variables.

    Args:
        cps (h5py.File): The CPS dataset file.
        person (DataFrame): The CPS person table.
    """
    cps["e00200"] = person.WSAL_VAL
    cps["e00900"] = person.SEMP_VAL
    cps["e02100"] = person.FRSE_VAL
    cps["e02400"] = person.SS_VAL
    cps["e02300"] = person.UC_VAL

    # Pensions/annuities
    other_inc_type = person.OI_OFF
    cps["e01500"] = other_inc_type.isin((2, 13)) * person.OI_VAL

    # Alimony
    cps["e00800"] = (person.OI_OFF == 20) * person.OI_VAL


def add_SPM_variables(cps: h5py.File, spm_unit: DataFrame):
    cps["SPM_unit_net_income"] = spm_unit.SPM_RESOURCES
    cps["poverty_threshold"] = spm_unit.SPM_POVTHRESHOLD