# Taxonomy

This is a rudimentary tool for displaying the “parent taxon” statements of an item in a tree.
It was built during the [Wikidata Zurich Training event](https://www.wikidata.org/wiki/Wikidata:Events/Wikidata_Zurich_Training2019) (2019-11-03)
as a demonstration for how to create a tool.
It is not deployed on Toolforge, and I have no further plans for it.

## Local development setup

You can run the tool locally, which is very convenient for development
(for example, Flask will automatically reload the application any time you save a file).

```
git clone https://phabricator.wikimedia.org/source/tool-taxonomy.git
cd tool-taxonomy
pip3 install -r requirements.txt
FLASK_APP=app.py FLASK_ENV=development flask run
```

If you want, you can do this inside some virtualenv too.

## License

The code in this repository is released under the AGPL v3, as provided in the `LICENSE` file.
