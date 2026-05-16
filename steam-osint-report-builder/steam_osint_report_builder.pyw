from steam_osint.dependency_bootstrap import ensure_requirements


if __name__ == "__main__":
    ensure_requirements()
    from steam_osint.gui import main

    main()
