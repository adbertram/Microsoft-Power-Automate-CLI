"""
OpenAPI validation and manipulation commands.
"""

import json
from pathlib import Path
from typing import Optional

import typer
from openapi_spec_validator import validate_spec
from openapi_spec_validator.validation.exceptions import OpenAPIValidationError
from openapi_spec_validator import (
    OpenAPIV2SpecValidator,
    OpenAPIV30SpecValidator,
    OpenAPIV31SpecValidator
)

from ..output import print_success, print_error, print_info, print_warning

app = typer.Typer(help="OpenAPI specification validation and manipulation")


@app.command("validate")
def validate_openapi(
    spec_file: Path = typer.Argument(..., help="Path to OpenAPI/Swagger JSON or YAML file"),
    spec_version: Optional[str] = typer.Option("2.0", "--version", "-v", help="Force specific OpenAPI version (2.0, 3.0, 3.1). Defaults to 2.0 (Swagger) for Power Automate compatibility"),
    base_uri: str = typer.Option("", "--base-uri", "-b", help="Base URI for resolving $ref references"),
    show_details: bool = typer.Option(False, "--details", "-d", help="Show detailed validation errors"),
):
    """
    Validate an OpenAPI specification file.

    Supports:
    - Swagger 2.0 (OpenAPI 2.0) - DEFAULT for Power Automate compatibility
    - OpenAPI 3.0.x
    - OpenAPI 3.1.x

    The validator defaults to Swagger 2.0 (v2) as this is the format used by Power Automate
    custom connectors. Use --version to validate against OpenAPI 3.x specifications.

    Examples:
        # Validate as Swagger 2.0 (default for Power Automate)
        powerautomate openapi validate api-spec.json

        # Validate as OpenAPI 3.0
        powerautomate openapi validate spec.json --version 3.0

        # Validate with base URI for $ref resolution
        powerautomate openapi validate spec.json --base-uri "https://api.example.com"

        # Show detailed error messages
        powerautomate openapi validate spec.json --details
    """
    try:
        # Check if file exists
        if not spec_file.exists():
            print_error(f"File not found: {spec_file}")
            raise typer.Exit(1)

        # Read the spec file
        print_info(f"Reading spec file: {spec_file}")
        with open(spec_file, 'r') as f:
            if spec_file.suffix.lower() in ['.yaml', '.yml']:
                import yaml
                spec = yaml.safe_load(f)
            else:
                spec = json.load(f)

        # Determine validator class based on version
        validator_cls = None
        detected_version = None

        if 'swagger' in spec:
            detected_version = f"Swagger {spec.get('swagger', 'unknown')}"
            if spec_version == "2.0" or spec_version is None:
                validator_cls = OpenAPIV2SpecValidator
        elif 'openapi' in spec:
            openapi_version = spec.get('openapi', 'unknown')
            detected_version = f"OpenAPI {openapi_version}"

            if spec_version:
                # User specified version
                if spec_version == "3.0":
                    validator_cls = OpenAPIV30SpecValidator
                elif spec_version == "3.1":
                    validator_cls = OpenAPIV31SpecValidator
                elif spec_version == "2.0":
                    print_warning(f"Spec declares OpenAPI {openapi_version} but forcing Swagger 2.0 validation")
                    validator_cls = OpenAPIV2SpecValidator
            else:
                # Auto-detect from version string
                if openapi_version.startswith('3.0'):
                    validator_cls = OpenAPIV30SpecValidator
                elif openapi_version.startswith('3.1'):
                    validator_cls = OpenAPIV31SpecValidator
        else:
            print_error("Unable to determine OpenAPI/Swagger version from spec file")
            print_info("Spec must contain 'swagger' or 'openapi' field")
            raise typer.Exit(1)

        print_info(f"Detected version: {detected_version}")
        if validator_cls:
            print_info(f"Using validator: {validator_cls.__name__}")

        # Validate the spec
        print_info("Validating specification...")
        try:
            validate_spec(
                spec,
                base_uri=base_uri,
                cls=validator_cls,
                spec_url=str(spec_file.absolute())
            )

            print_success("✓ OpenAPI specification is valid!")
            print_info(f"  Version: {detected_version}")
            print_info(f"  File: {spec_file}")

            # Show some basic stats
            if 'paths' in spec:
                path_count = len(spec['paths'])
                print_info(f"  Paths: {path_count}")

            if 'components' in spec and 'schemas' in spec['components']:
                schema_count = len(spec['components']['schemas'])
                print_info(f"  Schemas: {schema_count}")
            elif 'definitions' in spec:
                schema_count = len(spec['definitions'])
                print_info(f"  Definitions: {schema_count}")

        except OpenAPIValidationError as e:
            print_error("✗ OpenAPI specification validation failed!")
            print_error(f"  File: {spec_file}")

            if show_details:
                print_error(f"\nValidation Error:\n{str(e)}")
            else:
                # Show just the main error message
                error_msg = str(e).split('\n')[0]
                print_error(f"  Error: {error_msg}")
                print_info("\nUse --details flag to see full validation error")

            raise typer.Exit(1)

    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON in spec file: {e}")
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {type(e).__name__}: {e}")
        raise typer.Exit(1)
