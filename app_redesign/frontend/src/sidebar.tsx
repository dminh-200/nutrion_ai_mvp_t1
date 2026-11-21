import { BarChart3, ClipboardCheck, Leaf, ShieldCheck, UserRound, Utensils, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { NativeSelect } from "@/components/ui/native-select";
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupContent, SidebarGroupLabel,
  SidebarHeader, SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarProvider, SidebarSeparator,
} from "@/components/ui/sidebar";
import { mount, type ComponentArgs } from "./mount";

type Model = {
  page: string;
  pages: string[];
  role: string;
  roles: string[];
  warningCount: number;
  sampleFood: boolean;
  warnings: string[];
};

const pages = {
  "Hồ sơ": UserRound,
  "Thực đơn": Utensils,
  "Bàn duyệt": ClipboardCheck,
  "Tổng quan vận hành": BarChart3,
};

function AppSidebar({ data, action }: { data: Model; action: ComponentArgs<Model>["setTriggerValue"] }) {
  return <SidebarProvider className="nutri-side-provider">
    <Sidebar collapsible="none" className="nutri-side">
      <SidebarHeader className="nutri-side-header">
        <div className="nutri-side-brand">
          <span><Leaf aria-hidden="true" /></span><div><strong>Nutri AI</strong><small>Cổng dinh dưỡng</small></div>
        </div>
        <Badge variant="secondary" className="nutri-side-demo">Dữ liệu giả lập</Badge>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup className="nutri-side-nav">
          <SidebarGroupLabel>Không gian làm việc</SidebarGroupLabel>
          <SidebarGroupContent>
            <nav aria-label="Điều hướng chính">
              <SidebarMenu>
                {data.pages.map((page) => {
                  const Icon = pages[page as keyof typeof pages];
                  return <SidebarMenuItem key={page}>
                    <SidebarMenuButton className="nutri-side-link" isActive={page === data.page}
                      aria-current={page === data.page ? "page" : undefined}
                      onClick={() => { if (page !== data.page) action("action", { page }); }}>
                      <Icon aria-hidden="true" /><span>{page}</span>
                      <ChevronRight className="nutri-side-chevron" aria-hidden="true" />
                    </SidebarMenuButton>
                  </SidebarMenuItem>;
                })}
              </SidebarMenu>
            </nav>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarSeparator className="nutri-side-rule" />
        <SidebarGroup className="nutri-side-role">
          <label htmlFor="nutri-demo-role">Vai trò demo</label>
          <NativeSelect id="nutri-demo-role" value={data.role}
            onChange={(event) => action("action", { role: event.currentTarget.value })}>
            {data.roles.map((role) => <option key={role}>{role}</option>)}
          </NativeSelect>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="nutri-side-footer">
        <details>
          <summary><ShieldCheck aria-hidden="true" /><span>
            {data.warningCount ? `${data.warningCount} quy tắc cần xác minh` : "Thông tin bản thử"}
            {data.sampleFood && <small>Đang dùng dữ liệu thực phẩm mẫu</small>}
          </span><ChevronRight aria-hidden="true" /></summary>
          <p>Mô hình giả lập · 0 API thật · DB tạm</p>
          <p>Vai trò demo dùng để mô phỏng hiển thị.</p>
          {data.warnings.length > 0 && <ul>{data.warnings.map((item) => <li key={item}>{item}</li>)}</ul>}
        </details>
      </SidebarFooter>
    </Sidebar>
  </SidebarProvider>;
}

export default function render({ data, parentElement, setTriggerValue }: ComponentArgs<Model>) {
  return mount(parentElement, ".nutri-sidebar-root", <AppSidebar data={data} action={setTriggerValue} />);
}
