from validate_blocklist import check_line


class TestCheckLine:
    def test_valid_rule_no_errors(self):
        errors, domain = check_line("||poki.com^", 1, set())
        assert errors == []
        assert domain == "poki.com"

    def test_blank_and_comment_lines_ignored(self):
        errors, domain = check_line("", 1, set())
        assert errors == [] and domain is None

        errors, domain = check_line("# comentario", 1, set())
        assert errors == [] and domain is None

    def test_invalid_syntax_missing_prefix(self):
        errors, domain = check_line("poki.com^", 1, set())
        assert len(errors) == 1
        assert domain is None

    def test_invalid_syntax_missing_suffix(self):
        errors, domain = check_line("||poki.com", 1, set())
        assert len(errors) == 1
        assert domain is None

    def test_duplicate_domain_detected(self):
        seen = {"poki.com"}
        errors, domain = check_line("||poki.com^", 2, seen)
        assert any("duplicado" in e for e in errors)

    def test_whitelisted_domain_flagged_critical(self):
        errors, domain = check_line("||google.com^", 1, set())
        assert any("CRÍTICO" in e for e in errors)

    def test_whitelisted_subdomain_flagged_critical(self):
        errors, domain = check_line("||mail.google.com^", 1, set())
        assert any("CRÍTICO" in e for e in errors)

    def test_invalid_domain_format_flagged(self):
        errors, domain = check_line("||not a domain!^", 1, set())
        assert any("Formato de dominio no válido" in e for e in errors)

    def test_path_rule_with_document_modifier_allowed(self):
        errors, domain = check_line("||sites.google.com/view/game/*$document", 1, set())
        assert errors == []
        assert domain is None

    def test_path_rule_without_prefix_rejected(self):
        errors, domain = check_line("sites.google.com/view/game/*$document", 1, set())
        assert len(errors) == 1

    def test_www_prefix_rejected(self):
        errors, domain = check_line("||www.friv2010.com^", 1, set())
        assert any("www." in e for e in errors)
        assert domain == "www.friv2010.com"
