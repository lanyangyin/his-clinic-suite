from PySide6.QtWidgets import QApplication


def test_pagination_bar_page_size_and_jump():
    from his_client.ui.pagination import PaginationBar

    app = QApplication.instance() or QApplication([])
    bar = PaginationBar((20, 50, 100))
    bar.set_total(101)
    assert bar.page_count() == 6
    bar.set_page(6)
    assert bar.page() == 6
    bar.size_combo.setCurrentIndex(1)
    app.processEvents()
    assert bar.page_size() == 50
    assert bar.page() == 1
    assert bar.page_count() == 3
