"""Explicit owner delegation, up to three child tasks with reduced capabilities."""

from hanh_dong import active_actor


class PhoiHop:
    def __init__(self, kho, core, tasks):
        self.kho, self.core, self.tasks = kho, core, tasks
        with kho.ket_noi() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS child_tasks(parent_id TEXT,child_id TEXT UNIQUE,recipient TEXT)"
            )

    def list(self, actor, parent_id):
        self.tasks.detail(actor, parent_id)
        with self.kho.ket_noi() as db:
            rows = db.execute(
                "SELECT * FROM child_tasks WHERE parent_id=?", (parent_id,)
            ).fetchall()
        result = []
        for r in rows:
            # Parent owner/admin must separately be permitted to inspect child output.
            try:
                result.append(
                    {
                        "recipient": r["recipient"],
                        "task": self.tasks.detail(actor, r["child_id"]),
                    }
                )
            except ValueError:
                result.append(
                    {
                        "recipient": r["recipient"],
                        "task": {"id": r["child_id"], "status": "private"},
                    }
                )
        return {"children": result}

    def delegate(self, actor, args):
        parent = self.tasks.detail(actor, args.get("task_id", ""))
        if (
            actor["role"] != "quan-tri"
            or parent["owner"] != actor["id"]
            or not parent.get("allow_delegation")
            or parent.get("parent_id")
        ):
            raise PermissionError("Tác vụ chưa cấp quyền điều phối agent")
        recipient = active_actor(self.kho, args.get("recipient"))
        if recipient["role"] != "operator":
            raise ValueError("Cần danh tính vận hành đang hoạt động")
        with self.kho.ket_noi() as db:
            if (
                db.execute(
                    "SELECT count(*) FROM child_tasks WHERE parent_id=?",
                    (parent["id"],),
                ).fetchone()[0]
                >= 3
            ):
                raise ValueError("Tối đa ba tác vụ con")
        # Context is re-authorized for the recipient, never copied around project ACLs.
        task_args = {
            "prompt": args.get("prompt"),
            "module_ids": parent["module_ids"],
            "project_id": parent.get("project_id", ""),
            "document_ids": [d["id"] for d in parent.get("documents", [])],
            "allow_python": parent.get("allow_python", False),
            "browser_hosts": parent.get("browser_hosts", []),
        }
        response = self.core.goi(recipient, "cong_viec.tao", task_args)
        if not response.get("ok"):
            raise ValueError("Agent chưa có quyền hoặc chưa nhận được tác vụ")
        identifier = response["ket_qua"]["id"]
        with self.tasks.lock:
            child = self.tasks.detail(recipient, identifier)
            child["parent_id"] = parent["id"]
            self.tasks._save(child)
        with self.kho.ket_noi() as db:
            db.execute(
                "INSERT INTO child_tasks VALUES (?,?,?)",
                (parent["id"], identifier, recipient["id"]),
            )
        self.kho.su_kien(actor["id"], "giao-tac-vu-con", identifier)
        return {
            "id": identifier,
            "recipient": recipient["id"],
            "parent_id": parent["id"],
        }
