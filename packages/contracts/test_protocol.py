import unittest

from protocol import ExerciseConfig, merge_restrictions, validate_prescription


class ProtocolContractTests(unittest.TestCase):
    def test_specific_restriction_wins_and_provenance_is_retained(self) -> None:
        result = merge_restrictions(
            base={"target_rom_degrees": 90},
            clinic={"target_rom_degrees": 80},
            individual={"target_rom_degrees": 70},
        )
        self.assertEqual(result["target_rom_degrees"], 70)
        self.assertEqual(
            [item["source"] for item in result["restriction_sources"]],
            ["phoenix_base_template", "clinic_or_surgeon_template", "individual_clinician"],
        )

    def test_draft_definition_requires_all_protocol_fields(self) -> None:
        config = ExerciseConfig("heel_slide", "Heel Slide", "early", "supine", {})
        self.assertTrue(config.validate())

    def test_prescription_does_not_allow_invalid_shape(self) -> None:
        self.assertTrue(validate_prescription({"sets": 0, "target_rom_degrees": 181}))


if __name__ == "__main__":
    unittest.main()
